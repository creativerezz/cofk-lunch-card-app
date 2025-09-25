"""
NFC Card Service Layer
Handles all NFC card operations with encryption and offline support
"""

import json
import time
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Tuple
from cryptography.fernet import Fernet
from smartcard.System import readers
from smartcard.util import toHexString, toBytes
import hashlib
import base64

class NFCCardService:
    """Service for interacting with NFC cards"""
    
    # NFC Commands
    GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
    
    # Mifare Classic commands for data storage
    AUTH_KEY_A = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00]  # + block + key type + key
    READ_BLOCK = [0xFF, 0xB0, 0x00]  # + block + length
    WRITE_BLOCK = [0xFF, 0xD6, 0x00]  # + block + length + data
    
    # Data storage configuration
    BALANCE_BLOCK = 4  # Store balance in block 4
    STUDENT_ID_BLOCK = 5  # Store student ID in block 5
    CHECKSUM_BLOCK = 6  # Store checksum for validation
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize NFC service with optional encryption"""
        self.reader = None
        self.connection = None
        
        # Setup encryption
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            # Generate a new key if not provided
            key = Fernet.generate_key()
            self.cipher = Fernet(key)
            print(f"Generated encryption key: {key.decode()}")
        
        # Setup offline storage
        self.offline_db_path = "database/offline_cards.db"
        self.init_offline_db()
    
    def init_offline_db(self):
        """Initialize offline database for card data caching"""
        conn = sqlite3.connect(self.offline_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_cache (
                card_uid TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                student_id TEXT,
                last_sync TIMESTAMP,
                checksum TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_uid TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced BOOLEAN DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def connect_reader(self) -> bool:
        """Connect to NFC reader"""
        try:
            r = readers()
            if not r:
                print("No NFC reader found")
                return False
            
            self.reader = r[0]
            print(f"Connected to reader: {self.reader}")
            return True
            
        except Exception as e:
            print(f"Error connecting to reader: {e}")
            return False
    
    def wait_for_card(self, timeout: int = 30) -> Optional[str]:
        """Wait for a card to be presented"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                self.connection = self.reader.createConnection()
                self.connection.connect()
                
                # Get card UID
                data, sw1, sw2 = self.connection.transmit(self.GET_UID)
                if sw1 == 0x90 and sw2 == 0x00:
                    uid = toHexString(data)
                    return uid
                    
            except Exception:
                time.sleep(0.5)
                continue
        
        return None
    
    def read_card(self, card_uid: Optional[str] = None) -> Optional[Dict]:
        """Read card data (balance, student ID, etc.)"""
        try:
            # If no card UID provided, wait for card
            if not card_uid:
                card_uid = self.wait_for_card()
                if not card_uid:
                    return None
            
            # Try to read from physical card first
            card_data = self._read_physical_card()
            
            if card_data:
                # Update offline cache
                self._update_offline_cache(card_uid, card_data)
                return card_data
            else:
                # Fallback to offline cache
                return self._read_offline_cache(card_uid)
                
        except Exception as e:
            print(f"Error reading card: {e}")
            # Fallback to offline cache
            if card_uid:
                return self._read_offline_cache(card_uid)
            return None
    
    def _read_physical_card(self) -> Optional[Dict]:
        """Read data directly from physical NFC card"""
        try:
            if not self.connection:
                return None
            
            # Authenticate with default key (change in production!)
            default_key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
            auth_cmd = self.AUTH_KEY_A + [self.BALANCE_BLOCK, 0x60] + default_key
            data, sw1, sw2 = self.connection.transmit(auth_cmd)
            
            if sw1 != 0x90 or sw2 != 0x00:
                print("Authentication failed")
                return None
            
            # Read balance block
            read_cmd = self.READ_BLOCK + [self.BALANCE_BLOCK, 0x10]
            data, sw1, sw2 = self.connection.transmit(read_cmd)
            
            if sw1 == 0x90 and sw2 == 0x00:
                # Decrypt and parse balance data
                balance_data = bytes(data[:8])
                balance = self._decrypt_balance(balance_data)
                
                # Read student ID block
                read_cmd = self.READ_BLOCK + [self.STUDENT_ID_BLOCK, 0x10]
                data, sw1, sw2 = self.connection.transmit(read_cmd)
                student_id = None
                
                if sw1 == 0x90 and sw2 == 0x00:
                    student_id_data = bytes(data[:16])
                    student_id = student_id_data.decode('utf-8').strip('\x00')
                
                return {
                    'balance': balance,
                    'student_id': student_id,
                    'last_read': datetime.utcnow().isoformat()
                }
            
            return None
            
        except Exception as e:
            print(f"Error reading physical card: {e}")
            return None
    
    def write_card(self, card_uid: str, balance: Decimal, 
                  student_id: Optional[str] = None) -> bool:
        """Write data to NFC card"""
        try:
            # Ensure we have a connection
            if not self.connection:
                detected_uid = self.wait_for_card()
                if detected_uid != card_uid:
                    print(f"Wrong card presented. Expected {card_uid}, got {detected_uid}")
                    return False
            
            # Write to physical card
            success = self._write_physical_card(balance, student_id)
            
            # Always update offline cache
            self._update_offline_cache(card_uid, {
                'balance': float(balance),
                'student_id': student_id
            })
            
            return success
            
        except Exception as e:
            print(f"Error writing to card: {e}")
            # Still update offline cache even if physical write fails
            self._update_offline_cache(card_uid, {
                'balance': float(balance),
                'student_id': student_id
            })
            return False
    
    def _write_physical_card(self, balance: Decimal, 
                            student_id: Optional[str] = None) -> bool:
        """Write data directly to physical NFC card"""
        try:
            if not self.connection:
                return False
            
            # Authenticate
            default_key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
            auth_cmd = self.AUTH_KEY_A + [self.BALANCE_BLOCK, 0x60] + default_key
            data, sw1, sw2 = self.connection.transmit(auth_cmd)
            
            if sw1 != 0x90 or sw2 != 0x00:
                return False
            
            # Prepare and encrypt balance data
            balance_bytes = self._encrypt_balance(balance)
            
            # Write balance (16 bytes per block)
            write_data = list(balance_bytes[:16])
            while len(write_data) < 16:
                write_data.append(0x00)
            
            write_cmd = self.WRITE_BLOCK + [self.BALANCE_BLOCK, 0x10] + write_data
            data, sw1, sw2 = self.connection.transmit(write_cmd)
            
            if sw1 != 0x90 or sw2 != 0x00:
                return False
            
            # Write student ID if provided
            if student_id:
                student_bytes = student_id.encode('utf-8')[:16]
                write_data = list(student_bytes)
                while len(write_data) < 16:
                    write_data.append(0x00)
                
                write_cmd = self.WRITE_BLOCK + [self.STUDENT_ID_BLOCK, 0x10] + write_data
                data, sw1, sw2 = self.connection.transmit(write_cmd)
            
            # Write checksum for validation
            checksum = self._calculate_checksum(balance, student_id)
            checksum_bytes = checksum.encode('utf-8')[:16]
            write_data = list(checksum_bytes)
            while len(write_data) < 16:
                write_data.append(0x00)
            
            write_cmd = self.WRITE_BLOCK + [self.CHECKSUM_BLOCK, 0x10] + write_data
            data, sw1, sw2 = self.connection.transmit(write_cmd)
            
            return True
            
        except Exception as e:
            print(f"Error writing to physical card: {e}")
            return False
    
    def _encrypt_balance(self, balance: Decimal) -> bytes:
        """Encrypt balance for storage on card"""
        # Convert balance to string with 2 decimal places
        balance_str = f"{balance:.2f}"
        # Pad to ensure consistent length
        padded = balance_str.ljust(16, '\x00')
        # Simple XOR encryption (use stronger encryption in production!)
        key = 0xA5
        encrypted = bytes([ord(c) ^ key for c in padded])
        return encrypted
    
    def _decrypt_balance(self, encrypted_data: bytes) -> Decimal:
        """Decrypt balance from card"""
        try:
            # Simple XOR decryption
            key = 0xA5
            decrypted = bytes([b ^ key for b in encrypted_data])
            balance_str = decrypted.decode('utf-8').strip('\x00')
            return Decimal(balance_str)
        except Exception:
            return Decimal('0.00')
    
    def _calculate_checksum(self, balance: Decimal, 
                           student_id: Optional[str] = None) -> str:
        """Calculate checksum for data validation"""
        data = f"{balance:.2f}:{student_id or ''}"
        checksum = hashlib.md5(data.encode()).hexdigest()[:8]
        return checksum
    
    def _update_offline_cache(self, card_uid: str, data: Dict):
        """Update offline cache with card data"""
        conn = sqlite3.connect(self.offline_db_path)
        cursor = conn.cursor()
        
        checksum = self._calculate_checksum(
            Decimal(str(data['balance'])),
            data.get('student_id')
        )
        
        cursor.execute('''
            INSERT OR REPLACE INTO card_cache 
            (card_uid, balance, student_id, last_sync, checksum)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            card_uid,
            data['balance'],
            data.get('student_id'),
            datetime.utcnow(),
            checksum
        ))
        
        conn.commit()
        conn.close()
    
    def _read_offline_cache(self, card_uid: str) -> Optional[Dict]:
        """Read card data from offline cache"""
        conn = sqlite3.connect(self.offline_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT balance, student_id, last_sync 
            FROM card_cache 
            WHERE card_uid = ?
        ''', (card_uid,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'balance': Decimal(str(row[0])),
                'student_id': row[1],
                'last_sync': row[2],
                'from_cache': True
            }
        
        return None
    
    def add_offline_transaction(self, card_uid: str, 
                               transaction_type: str, 
                               amount: Decimal):
        """Add transaction to offline queue for later sync"""
        conn = sqlite3.connect(self.offline_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO pending_transactions 
            (card_uid, transaction_type, amount)
            VALUES (?, ?, ?)
        ''', (card_uid, transaction_type, float(amount)))
        
        conn.commit()
        conn.close()
    
    def get_pending_transactions(self) -> list:
        """Get all pending offline transactions"""
        conn = sqlite3.connect(self.offline_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, card_uid, transaction_type, amount, timestamp
            FROM pending_transactions
            WHERE synced = 0
            ORDER BY timestamp
        ''')
        
        transactions = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': t[0],
                'card_uid': t[1],
                'transaction_type': t[2],
                'amount': Decimal(str(t[3])),
                'timestamp': t[4]
            }
            for t in transactions
        ]
    
    def mark_transaction_synced(self, transaction_id: int):
        """Mark offline transaction as synced"""
        conn = sqlite3.connect(self.offline_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pending_transactions
            SET synced = 1
            WHERE id = ?
        ''', (transaction_id,))
        
        conn.commit()
        conn.close()
    
    def disconnect(self):
        """Disconnect from reader"""
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass
            self.connection = None

# Singleton instance
nfc_service = None

def get_nfc_service(encryption_key: Optional[str] = None) -> NFCCardService:
    """Get or create NFC service instance"""
    global nfc_service
    if not nfc_service:
        nfc_service = NFCCardService(encryption_key)
    return nfc_service