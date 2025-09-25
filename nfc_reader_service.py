#!/usr/bin/env python3
"""
NFC Reader Service for ACR122U
Monitors NFC cards and stores readings in SQLite database
"""

import sqlite3
import time
import sys
from datetime import datetime
from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.CardConnectionObserver import ConsoleCardConnectionObserver

class NFCReaderService:
    def __init__(self, db_path="nfc_readings.db"):
        """Initialize the NFC reader service"""
        self.db_path = db_path
        self.reader = None
        self.connection = None
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database with readings table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for NFC readings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_uid TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                card_type TEXT,
                data TEXT
            )
        ''')
        
        # Create table for registered cards (optional)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registered_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_uid TEXT UNIQUE NOT NULL,
                owner_name TEXT,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✓ Database initialized at {self.db_path}")
        
    def connect_reader(self):
        """Connect to ACR122U NFC reader"""
        try:
            # Get all available readers
            r = readers()
            
            if not r:
                print("❌ No smart card readers found!")
                print("Please ensure your ACR122U reader is connected.")
                return False
                
            print(f"✓ Found {len(r)} reader(s):")
            for i, reader in enumerate(r):
                print(f"  [{i}] {reader}")
                
            # Use the first reader (usually ACR122U)
            self.reader = r[0]
            print(f"\n✓ Using reader: {self.reader}")
            return True
            
        except Exception as e:
            print(f"❌ Error connecting to reader: {e}")
            return False
            
    def get_card_uid(self, connection):
        """Get UID from the connected card"""
        try:
            # Get UID command for most NFC cards
            GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(GET_UID)
            
            if sw1 == 0x90 and sw2 == 0x00:
                uid = toHexString(data)
                return uid
            else:
                return None
                
        except Exception as e:
            print(f"Error reading card UID: {e}")
            return None
            
    def save_reading(self, card_uid, card_type="Unknown"):
        """Save card reading to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO card_readings (card_uid, card_type, data)
                VALUES (?, ?, ?)
            ''', (card_uid, card_type, f"Read at {datetime.now()}"))
            
            conn.commit()
            conn.close()
            
            print(f"  💾 Saved to database")
            
        except Exception as e:
            print(f"  ❌ Database error: {e}")
            
    def monitor_cards(self):
        """Main loop to monitor NFC cards"""
        print("\n🔄 Starting NFC monitoring service...")
        print("Place an NFC card on the reader (Ctrl+C to stop)\n")
        
        last_card_uid = None
        card_present = False
        
        try:
            while True:
                try:
                    # Try to connect to a card
                    connection = self.reader.createConnection()
                    connection.connect()
                    
                    # Get card UID
                    uid = self.get_card_uid(connection)
                    
                    if uid:
                        if uid != last_card_uid or not card_present:
                            # New card detected
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            print(f"🎫 Card detected at {timestamp}")
                            print(f"  UID: {uid}")
                            
                            # Save to database
                            self.save_reading(uid)
                            
                            last_card_uid = uid
                            card_present = True
                            
                    connection.disconnect()
                    
                except Exception as e:
                    # No card present or card removed
                    if card_present:
                        print("  Card removed\n")
                        card_present = False
                        last_card_uid = None
                        
                # Small delay to prevent CPU overload
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n\n⏹  Stopping NFC reader service...")
            self.show_statistics()
            
    def show_statistics(self):
        """Show statistics from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total readings
            cursor.execute("SELECT COUNT(*) FROM card_readings")
            total = cursor.fetchone()[0]
            
            # Get unique cards
            cursor.execute("SELECT COUNT(DISTINCT card_uid) FROM card_readings")
            unique = cursor.fetchone()[0]
            
            # Get recent readings
            cursor.execute("""
                SELECT card_uid, COUNT(*) as count 
                FROM card_readings 
                GROUP BY card_uid 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_cards = cursor.fetchall()
            
            conn.close()
            
            print("\n📊 Session Statistics:")
            print(f"  Total readings: {total}")
            print(f"  Unique cards: {unique}")
            
            if top_cards:
                print("\n  Top cards by frequency:")
                for uid, count in top_cards:
                    print(f"    {uid}: {count} reading(s)")
                    
        except Exception as e:
            print(f"Error showing statistics: {e}")

def main():
    """Main entry point"""
    print("=" * 50)
    print("NFC READER SERVICE - ACR122U")
    print("=" * 50)
    
    # Create and start the service
    service = NFCReaderService()
    
    # Connect to reader
    if not service.connect_reader():
        print("\nPlease check your reader connection and try again.")
        sys.exit(1)
        
    # Start monitoring
    service.monitor_cards()
    
    print("\nService stopped. Goodbye!")

if __name__ == "__main__":
    main()