# Quick Setup Guide for Ranking System

## Step 1: Install Python Dependencies

```powershell
pip install -r requirements.txt
```

## Step 2: Install Tesseract OCR

### Windows (Easiest Method):

1. **Download Tesseract Installer:**
   - Visit: https://github.com/UB-Mannheim/tesseract/wiki
   - Download latest installer (e.g., `tesseract-ocr-w64-setup-5.3.3.exe`)

2. **Run Installer:**
   - Install to default location: `C:\Program Files\Tesseract-OCR`
   - Check "Add to PATH" option if available

3. **Verify Installation:**
   ```powershell
   tesseract --version
   ```
   
   Should show: `tesseract 5.x.x`

### Alternative: Chocolatey

```powershell
choco install tesseract
```

## Step 3: Test OCR

```powershell
python -c "import pytesseract; print('✅ pytesseract installed'); print('Version:', pytesseract.get_tesseract_version())"
```

## Step 4: Integration

Add to your `integrations/integration_loader.py`:

```python
# Add imports at top
from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine

# In __init__ method, add:
self.ranking_processor = ScreenshotProcessor()
self.ranking_storage = RankingStorageEngine("data/event_rankings.db")

# In _mount_cogs method, add:
from discord_bot.cogs.ranking_cog import setup as setup_ranking_cog

await setup_ranking_cog(
    self.bot,
    processor=self.ranking_processor,
    storage=self.ranking_storage
)

# Update the mounted cogs log message
logger.info("⚙️ Mounted cogs: translation, admin, help, role_management, sos, easteregg, game, battle, ranking")
```

## Step 5: Run Bot

```powershell
python main.py
```

## Commands Available

After bot starts, use:

- `/games ranking submit` - Submit a ranking screenshot
- `/games ranking view` - View your submission history  
- `/games ranking leaderboard` - View guild leaderboard

## Testing

1. Take a screenshot of your Top Heroes ranking
2. Make sure it shows:
   - Stage type (Prep/War)
   - Day number (1-5 buttons)
   - Your rank and score
   - Your player name with [TAO] tag

3. Run: `/games ranking submit`
4. Upload screenshot
5. Select day and stage
6. Bot will process and show extracted data!

## Troubleshooting

### "OCR not available" error:
- Make sure Tesseract is installed: `tesseract --version`
- Make sure pytesseract is installed: `pip list | findstr pytesseract`
- Restart terminal/IDE after installing Tesseract

### Can't find tesseract.exe:
Add this to the top of `screenshot_processor.py`:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Screenshot processing fails:
- Make sure image is clear and not blurry
- Check that rank and score are visible
- Try a different screenshot with better lighting
- Check bot logs for detailed error message

## Database Location

Rankings are stored in: `data/event_rankings.db` (created automatically)

You can view the database with:
- DB Browser for SQLite: https://sqlitebrowser.org/
- Or any SQLite viewer

## Need Help?

Check `RANKING_SYSTEM.md` for complete documentation!
