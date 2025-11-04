# KVK Visual Parsing System - Quick Setup Guide

## Installation Steps

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `Pillow>=9.0.0` - Image processing
- `pytesseract>=0.3.10` - OCR text extraction
- `opencv-python>=4.5.0` - Computer vision

### 2. Install Tesseract OCR Binary

**Windows:**
```bash
# Using Chocolatey
choco install tesseract

# Or download from: https://github.com/UB-Mannheim/tesseract/wiki
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Verify Installation:**
```bash
tesseract --version
```

### 3. Configure Environment Variables

Add to your `.env` file:
```env
# KVK Visual System
RANKINGS_CHANNEL_ID=your_rankings_channel_id
MODLOG_CHANNEL_ID=your_modlog_channel_id
```

### 4. Test System

Run the test script to verify everything works:
```bash
python scripts/test_kvk_visual_system.py
```

Expected output:
```
🔍 Testing KVK Visual Parsing System
==================================================
📦 Initializing KVK Visual Manager...
🔧 Checking system status...
System active: True
Dependencies available: True
Directories ready: True
✅ KVK Visual System test completed!
```

### 5. Start the Bot

```bash
python main.py
```

## Discord Commands

Once the bot is running, these commands are available:

### User Commands
- **`/kvk submit`** - Submit KVK ranking screenshot with visual parsing
- **`/kvk status`** - Check your comparison status vs power-band peers  
- **`/kvk power <level>`** - Set your power level for comparison tracking

### Admin Commands
- **`/kvk system`** - Check system health and diagnostics

## Initial Setup Workflow

### 1. Set Power Levels
Users should first set their power levels:
```
/kvk power 25000000
```
(for 25M power)

### 2. Submit Screenshots
Use `/kvk submit` in the rankings channel with KVK screenshots.

The system will automatically:
- Detect prep/war stage and day
- Extract all leaderboard data
- Identify your score row
- Update comparison tracking
- Save snapshot for analytics

### 3. Check Status
Use `/kvv status` to see:
- Current scores for prep/war stages
- Your rank within power band peers
- Progress vs similar players

## Troubleshooting

### "Dependencies not available"
1. Install missing packages: `pip install Pillow pytesseract opencv-python`
2. Install Tesseract binary (see step 2 above)
3. Restart the bot

### "Could not read text from image"
1. Ensure screenshot shows ranking data clearly
2. Try different image formats (PNG recommended)
3. Check image isn't too small (<100px) or too large (>4000px)

### "Could not identify self entry"
1. Make sure your row is visible in the screenshot
2. Check Discord display name matches in-game name
3. Report to admins if issue persists

### System Check
Admins can use `/kvk system` to diagnose:
- Component health status
- Dependency availability
- Cache file integrity
- Processing capabilities

## Directory Structure

The system creates these directories automatically:
```
uploads/screenshots/           # Screenshot storage
logs/                         # System logs and verification
logs/parsed_leaderboards/     # Complete ranking snapshots
cache/                        # User scores and comparisons
```

## Advanced Features

### Power Band Comparison
- Automatically tracks peers within ±10% power
- Calculates score and rank deltas
- Shows progression over time

### Visual Recognition
- Detects stage (prep vs war) from UI elements
- Identifies specific prep days (1-5 or overall)
- Extracts kingdom ID and all visible scores

### Data Validation
- Verifies stage matches selected mode
- Validates day numbers for prep stage
- Ensures consistent data extraction

### Analytics Storage
- Saves complete leaderboard snapshots
- Maintains comparison history
- Provides audit trail for all operations

## Support

For issues or questions:
1. Check the full documentation: `docs/KVK_VISUAL_PARSING_SYSTEM.md`
2. Run diagnostics: `/kvk system` (admin only)
3. Check logs in `logs/kvk_verification.log`
4. Test system: `python scripts/test_kvk_visual_system.py`

## Next Steps

After setup:
1. Encourage users to set power levels with `/kvk power`
2. Start submitting KVK screenshots with `/kvk submit`
3. Monitor system health with `/kvk system`
4. Review analytics in `logs/parsed_leaderboards/`