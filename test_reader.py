#!/usr/bin/env python3
"""
Test script to check NFC reader connectivity
"""

import sys
try:
    from smartcard.System import readers
    from smartcard.util import toHexString
except ImportError:
    print("❌ pyscard not installed. Please run: pip install pyscard")
    sys.exit(1)

def test_reader():
    """Test NFC reader connection"""
    print("Testing NFC Reader Connection")
    print("-" * 40)
    
    # Check for PC/SC service
    print("\n1. Checking for smart card readers...")
    
    try:
        # Get all readers
        r = readers()
        
        if not r:
            print("❌ No smart card readers found!")
            print("\nPossible solutions:")
            print("1. Make sure your ACR122U reader is connected via USB")
            print("2. On macOS, you may need to:")
            print("   a. Install the ACR122U driver from ACS website")
            print("   b. Start the PC/SC service: sudo killall -9 pcscd (to restart)")
            print("3. Try unplugging and reconnecting the reader")
            print("\nTo check if the reader is connected:")
            print("   ioreg -p IOUSB | grep -i acr")
            return False
            
        print(f"✅ Found {len(r)} reader(s):")
        for i, reader in enumerate(r):
            print(f"   [{i}] {reader}")
            
        # Try to connect to the first reader
        print("\n2. Testing connection to first reader...")
        reader = r[0]
        
        try:
            connection = reader.createConnection()
            connection.connect()
            print(f"✅ Successfully connected to: {reader}")
            
            # Try to get ATR (Answer To Reset)
            print("\n3. Getting ATR (Answer To Reset)...")
            atr = connection.getATR()
            print(f"   ATR: {toHexString(atr)}")
            
            connection.disconnect()
            print("\n✅ Reader test successful!")
            return True
            
        except Exception as e:
            print(f"⚠️  Could connect to reader but no card present: {e}")
            print("   This is normal - place a card on the reader to read it.")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nThis might be a PC/SC service issue.")
        print("Try running: sudo killall -9 pcscd")
        return False

if __name__ == "__main__":
    print("=" * 40)
    print("NFC READER CONNECTION TEST")
    print("=" * 40)
    
    success = test_reader()
    
    if success:
        print("\n✅ Your reader is ready to use!")
        print("You can now run: python3 nfc_reader_service.py")
    else:
        print("\n❌ Please resolve the issues above and try again.")
        
    print("\n" + "=" * 40)