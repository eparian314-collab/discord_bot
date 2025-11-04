# KVK Visual Parsing System Documentation

## Overview

The KVK Visual Parsing System is an advanced screenshot analysis solution for Top Heroes Kingdom vs Kingdom (KVK) ranking submissions. It provides intelligent visual recognition of UI elements, automatic data extraction, and power-band comparison tracking.

## Architecture

The system consists of three main components:

### 1. KVK Image Parser (`kvk_image_parser.py`)
**Purpose**: Visual-aware screenshot parser that extracts ranking data using OCR and computer vision.

**Key Features**:
- Stage detection (Prep vs War) from UI elements
- Day detection (1-5 or Overall) from button highlights
- Leaderboard row parsing with player names, ranks, and scores
- Self-entry identification through visual highlighting
- Kingdom ID extraction
- Data validation and verification logging

**Processing Phases**:
1. **Stage & Day Detection** - Analyzes UI toggle states and highlighted buttons
2. **Row Parsing** - Extracts all visible leaderboard entries
3. **Self-Score Identification** - Identifies the submitting user's row
4. **Data Validation** - Ensures extracted data is consistent

### 2. KVK Comparison Engine (`kvk_comparison_engine.py`)
**Purpose**: Manages power-band comparisons and rank analysis for peer tracking.

**Key Features**:
- Power level management (±10% similarity bands)
- Score delta calculations between peers
- Rank progression tracking
- Automated comparison updates after screenshot parsing
- Historical comparison data caching

**Workflow**:
1. Load user power levels and identify peers within ±10% power
2. Fetch current scores for all peers in the same stage/day
3. Compute score and rank deltas
4. Update comparison cache with results
5. Generate analysis summary

### 3. KVK Visual Manager (`kvk_visual_manager.py`)
**Purpose**: Main orchestrator that coordinates the complete parsing workflow.

**Complete Workflow**:
1. **Image Validation** - Check screenshot quality and content
2. **Visual Parsing** - Extract all ranking data with stage/day detection
3. **Score Synchronization** - Update user's personal score tracking
4. **Leaderboard Snapshots** - Save complete ranking context for analytics
5. **Comparison Updates** - Trigger peer analysis and delta calculations
6. **Verification Logging** - Record all operations for audit trail

## Discord Integration

### Enhanced KVK Ranking Cog (`kvk_visual_cog.py`)
Provides Discord slash commands for the visual parsing system:

#### Commands

**`/kvk submit`**
- Submit KVK ranking screenshots with enhanced visual parsing
- Automatically detects stage, day, and extracts all visible data
- Identifies submitter's score row and updates tracking
- Triggers comparison analysis with power-band peers

**`/kvk status`**
- View current comparison status vs power-band peers
- Shows prep and war stage progress
- Displays peer ranking and score deltas

**`/kvk power <level>`**
- Set personal power level for comparison tracking
- Enables automatic peer matching within ±10% power bands
- Required for comparison system participation

**`/kvk system`** (Admin only)
- Check system health and diagnostics
- View dependency status and cache file states
- Monitor processing capabilities

## Data Storage Structure

### Cache Files
Located in `cache/` directory:

**`kvk_scores.json`**
```json
{
  "user_id": {
    "prep": {
      "1": 5000000,
      "2": 8000000,
      "3": 12000000,
      "4": 15000000,
      "5": 18000000,
      "overall": 25000000
    },
    "war": {
      "war_day": 30000000
    }
  }
}
```

**`user_power_levels.json`**
```json
{
  "user_id": 25000000,
  "user_id2": 28000000
}
```

**`kvk_compare_pairs.json`**
```json
{
  "user_id_prep_3": {
    "user_id": "123456789",
    "stage_type": "prep",
    "prep_day": "3",
    "user_score": 12000000,
    "user_rank": 94,
    "user_power": 25000000,
    "peers": [
      {
        "user_id": "peer1",
        "username": "PeerPlayer",
        "power_level": 24000000,
        "current_score": 11500000,
        "score_delta": -500000,
        "rank_delta": 5
      }
    ],
    "analysis_timestamp": "2025-11-03T..."
  }
}
```

### Log Files
Located in `logs/` directory:

**`kvk_verification.log`**
- JSON-formatted log of all parsing attempts
- Success/failure status with timestamps
- Error messages and validation results

**`kvk_self_updates.log`**
- User score update history
- Stage, day, and point tracking
- Rank progression over time

**`kvk_comparison_updates.log`**
- Comparison analysis audit trail
- Peer count and delta summaries
- System performance metrics

### Snapshot Storage
**`logs/parsed_leaderboards/`**
- Complete leaderboard snapshots from each screenshot
- Filename format: `kingdom_XXXXX_day_N_YYYYMMDD_HHMMSS.json`
- Preserves full ranking context for analytics

## Visual Recognition Patterns

### Stage Detection
The parser identifies prep vs war stages using these UI patterns:
- **Prep Stage**: "prep stage", "preparation stage", "day 1-5" buttons
- **War Stage**: "war stage", "battle stage", "war day" indicators

### Day Detection
For prep stage, identifies specific days:
- **Day 1-5**: Highlighted button numbers or "day N" text
- **Overall**: "overall", "total", "all days", "summary" indicators

### Score Extraction
Recognizes various score formats:
- Comma-separated numbers: `14,422,335`
- Large numbers without commas: `14422335`
- Labeled scores: `points: 14,422,335` or `score: 14,422,335`

### Kingdom ID Extraction
Identifies kingdom references:
- Hash format: `#10435`
- Labeled format: `Kingdom: 10435`
- Short format: `K10435`

## Setup Requirements

### Dependencies
```bash
pip install Pillow>=9.0.0 pytesseract>=0.3.10 opencv-python>=4.5.0
```

### System Requirements
- **Tesseract OCR Binary**: Must be installed and accessible in system PATH
  - Windows: Download from GitHub releases or use `choco install tesseract`
  - Linux: `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`

### Directory Structure
The system automatically creates required directories:
```
uploads/screenshots/    # Screenshot storage
logs/                  # System logs
logs/parsed_leaderboards/  # Snapshot storage
cache/                 # User data and comparisons
```

### Configuration
Set these environment variables in `.env`:
```
RANKINGS_CHANNEL_ID=123456789012345678
MODLOG_CHANNEL_ID=123456789012345679
```

## Usage Examples

### Basic Screenshot Submission
1. User uploads screenshot in rankings channel
2. Use `/kvk submit` command with attached image
3. System automatically:
   - Detects prep day 3 from highlighted button
   - Extracts all visible leaderboard entries
   - Identifies user's row (rank #94, 7,948,885 points)
   - Updates user's prep day 3 score
   - Compares with power-band peers
   - Saves complete leaderboard snapshot

### Power Level Setup
```
/kvk power 25000000
```
Sets user's power to 25M for comparison tracking with peers in the 22.5M-27.5M range.

### Status Checking
```
/kvk status
```
Shows current prep and war scores, rank within power band, and peer comparison summary.

## Error Handling

### Validation Failures
- **Image too small/large**: Size limits enforced
- **No text detected**: OCR quality check
- **No ranking keywords**: Content validation
- **Stage mismatch**: UI consistency check

### Parsing Failures
- **No self-entry found**: Visual highlighting detection failed
- **Invalid day number**: Day 1-5 validation for prep stage
- **No scores extracted**: OCR pattern matching failed
- **Kingdom ID missing**: Context extraction failed

### System Diagnostics
Admin command `/kvk system` provides:
- Dependency availability status
- Directory structure validation
- Cache file health check
- Processing capability verification

## Performance Considerations

### OCR Processing
- Multiple OCR configurations tried for best results
- Image preprocessing enhances text recognition
- Processing time typically 2-5 seconds per screenshot

### Comparison Updates
- Triggered automatically after successful parsing
- Power band calculations cached for efficiency
- Peer data updated incrementally

### Storage Management
- Automatic cleanup of old snapshots (configurable retention)
- Compressed JSON storage for leaderboard data
- Log rotation to prevent disk space issues

## Future Enhancements

### Planned Features
1. **Visual Highlighting Detection**: Use computer vision to identify highlighted user rows
2. **Multi-Language Support**: OCR text recognition for different game languages
3. **Automated Rank Prediction**: Machine learning for rank progression forecasting
4. **Advanced Analytics**: Historical trend analysis and performance insights
5. **Export Capabilities**: CSV/Excel export for external analysis

### Technical Improvements
1. **Batch Processing**: Handle multiple screenshots simultaneously
2. **Cloud OCR Integration**: Backup OCR services for improved accuracy
3. **Real-time Updates**: WebSocket integration for live score tracking
4. **Mobile Optimization**: Enhanced parsing for mobile screenshot formats

## Troubleshooting

### Common Issues

**"Dependencies not available"**
- Install required packages: `pip install Pillow pytesseract opencv-python`
- Install Tesseract binary on system
- Verify PATH configuration

**"No text extracted from image"**
- Check screenshot quality and resolution
- Ensure ranking data is clearly visible
- Try different screenshot formats (PNG vs JPG)

**"Could not identify self entry"**
- Ensure your row is visible in the screenshot
- Check that username matches Discord display name
- Visual highlighting detection may need adjustment

**"No comparison data found"**
- Set power level first with `/kvk power`
- Other users need to set similar power levels
- Submit at least one screenshot to initialize tracking

### Admin Diagnostics
Use `/kvk system` to check:
- System component health
- Dependency installation status
- Cache file integrity
- Processing capabilities

## Integration Notes

### Event Bus Integration
The system integrates with HippoBot's event-driven architecture:
- Error reporting through `ENGINE_ERROR` topic
- Logging via centralized logging utilities
- Dependency injection through engine registry

### KVK Tracker Integration
Coordinates with existing KVK run management:
- Respects active/closed run windows
- Links submissions to specific KVK runs
- Supports admin late submissions

### Storage Integration
Works alongside existing ranking storage:
- Compatible with current ranking database schema
- Extends functionality without breaking changes
- Maintains audit trail compatibility