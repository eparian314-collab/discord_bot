# OCR Training Quick Start Guide

## 🚀 Getting Started in 3 Steps

### Step 1: Prepare Screenshots

Place your ranking screenshots in the `logs/screenshots` directory:

```powershell
# Create directory if it doesn't exist
New-Item -ItemType Directory -Path logs\screenshots -Force

# Copy your screenshots
Copy-Item "C:\path\to\your\rankings\*.png" logs\screenshots\
```

### Step 2: Enable Training

Set environment variable and start the bot:

```powershell
# Enable OCR training
$env:ENABLE_OCR_TRAINING="true"

# Start bot
python main.py
```

### Step 3: Train via DM

Bot will send you DMs for each screenshot. Reply with correct values:

**Bot's Message:**
```
🔍 Training Screenshot 1/3

📊 OCR Extracted Values:
Guild Tag: TAD
Player Name: Mars
Score: 25,200,103 pts
...

✏️ Reply with corrections:
```

**Your Reply:**
```
server_id: 10435
guild: TAO
player: Mars
score: 25200103
phase: prep
day: 3
rank: 94
```

**Bot Confirms:**
```
✅ Correction Saved
```

## 📝 Response Format

```
server_id: <number>
guild: <2-4 letters, uppercase>
player: <player name>
score: <number, no commas>
phase: prep or war
day: 1-5, overall, or none (for war)
rank: <number>
```

### Examples

**Prep Day 3:**
```
server_id: 10435
guild: TAO
player: Mars
score: 25200103
phase: prep
day: 3
rank: 94
```

**Prep Overall:**
```
server_id: 10435
guild: TAO
player: Mars
score: 80000000
phase: prep
day: overall
rank: 15
```

**War Stage:**
```
server_id: 10435
guild: TAO
player: Mars
score: 150000000
phase: war
day: none
rank: 8
```

## ⏭️ Skip Image

If you don't have the correct values or want to skip:

```
skip
```

## ✅ Completion

After processing all images:

```
✅ Training Session Complete

Processed: 3 screenshot(s)
Total corrections: 3
Learned patterns: 5

These corrections will be applied automatically to future submissions!
```

## 🔄 Run Training Again

To add more training data later:

1. Add new screenshots to `logs/screenshots`
2. Set `$env:ENABLE_OCR_TRAINING="true"`
3. Restart bot
4. Respond to new training prompts

## 🛑 Disable Training

After initial training, disable to speed up startup:

```powershell
# Disable training
$env:ENABLE_OCR_TRAINING="false"

# Or simply don't set the variable
python main.py
```

Learned corrections will still be applied!

## 📊 Check Training Data

View stored corrections:

```powershell
# View training data
Get-Content data\ocr_training.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

## 🐛 Troubleshooting

### Bot doesn't send DMs

- Check that OWNER_IDS is set correctly
- Ensure you can receive DMs from the bot
- Check bot logs for errors

### Training doesn't apply to submissions

- Verify `data/ocr_training.json` exists
- Check logs for "Applied training corrections"
- Ensure training engine is initialized (check startup logs)

### Wrong corrections applied

- Delete `data/ocr_training.json`
- Re-run training with correct values
- Or manually edit JSON to fix patterns

## 📚 Full Documentation

See `worfklow/architecture/OCR_TRAINING_SYSTEM.md` for complete details.

---

**Ready to train!** Add your screenshots and start the bot. 🎓
