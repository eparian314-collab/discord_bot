"""
Quick script to validate SOS channel configuration.
Run this to verify your .env settings before testing.
"""

import os

def load_env_file():
    """Load .env file manually."""
    env_vars = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    
    if not os.path.exists(env_path):
        print(f"❌ .env file not found at: {env_path}")
        return env_vars
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars

def validate_sos_config():
    """Validate SOS channel configuration."""
    print("=" * 60)
    print("🔍 SOS System Configuration Validator")
    print("=" * 60)
    print()
    
    # Load environment variables
    env_vars = load_env_file()
    
    if not env_vars:
        print("❌ Could not load .env file!")
        return False
    
    # Check SOS_CHANNEL_ID
    sos_channel_id = env_vars.get("SOS_CHANNEL_ID", "")
    
    if not sos_channel_id:
        print("❌ SOS_CHANNEL_ID not found in .env file!")
        print("   Add: SOS_CHANNEL_ID=your_channel_id")
        return False
    
    print(f"✅ SOS_CHANNEL_ID found: {sos_channel_id}")
    
    # Parse channel IDs
    channel_ids = [cid.strip() for cid in sos_channel_id.split(",") if cid.strip()]
    
    if not channel_ids:
        print("❌ No valid channel IDs found!")
        return False
    
    print(f"✅ Found {len(channel_ids)} SOS channel(s):")
    
    issues_found = False
    
    for i, channel_id_str in enumerate(channel_ids, 1):
        print(f"\n   Channel {i}: {channel_id_str}")
        
        # Check for trailing commas
        if channel_id_str.endswith(","):
            print(f"   ⚠️  Warning: Trailing comma found! Remove it.")
            issues_found = True
        
        # Validate it's a number
        try:
            channel_id = int(channel_id_str)
            print(f"   ✅ Valid Discord channel ID: {channel_id}")
            
            # Check length (Discord IDs are typically 17-19 digits)
            if len(channel_id_str) < 17 or len(channel_id_str) > 20:
                print(f"   ⚠️  Warning: ID length unusual ({len(channel_id_str)} digits)")
                print(f"      Discord IDs are usually 17-19 digits")
                issues_found = True
        except ValueError:
            print(f"   ❌ Invalid: Not a valid number!")
            issues_found = True
    
    print()
    print("=" * 60)
    
    # Check other related settings
    print("\n📋 Other Related Settings:")
    
    bot_channel = env_vars.get("BOT_CHANNEL_ID", "")
    if bot_channel:
        print(f"✅ BOT_CHANNEL_ID: {bot_channel}")
        if bot_channel.endswith(","):
            print("   ⚠️  Warning: Remove trailing comma!")
            issues_found = True
    else:
        print("⚠️  BOT_CHANNEL_ID not set (optional)")
    
    allowed_channels = env_vars.get("ALLOWED_CHANNELS", "")
    if allowed_channels:
        print(f"✅ ALLOWED_CHANNELS: {allowed_channels}")
        if allowed_channels.endswith(","):
            print("   ⚠️  Warning: Remove trailing comma!")
            issues_found = True
    else:
        print("⚠️  ALLOWED_CHANNELS not set")
    
    print()
    print("=" * 60)
    
    if issues_found:
        print("\n⚠️  WARNINGS FOUND - Please fix the issues above")
        print("\n💡 Fix trailing commas:")
        print("   Before: SOS_CHANNEL_ID=123456789,")
        print("   After:  SOS_CHANNEL_ID=123456789")
        print("\n💡 Multiple channels:")
        print("   Correct: SOS_CHANNEL_ID=123456789,987654321")
        print("   Wrong:   SOS_CHANNEL_ID=123456789,987654321,")
        return False
    else:
        print("\n✅ All checks passed! SOS configuration looks good!")
        print("\n📋 Next steps:")
        print("   1. Restart your bot: python -m discord_bot.main")
        print("   2. Test SOS with: /language sos add keyword:test phrase:Test alert")
        print("   3. Type 'test' in any channel")
        print("   4. Check SOS channel(s) for @everyone alert")
        print("   5. Users with language roles should get DMs")
        return True

if __name__ == "__main__":
    validate_sos_config()


