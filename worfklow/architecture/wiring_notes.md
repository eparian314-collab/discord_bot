# R8 Validation Wiring Guide

## Integration Points in RankingCog

### 1. Import Required Modules

Add to top of `discord_bot/cogs/ranking_cog.py`:

```python
from discord_bot.core.engines.validators import (
    score_confidence,
    phase_confidence,
    day_confidence,
    server_confidence,
    guild_confidence,
    name_confidence,
    overall_confidence,
    sanitize_and_validate
)
from discord_bot.core.engines.profile_cache import (
    get_player,
    upsert_player,
    prefer_cached_when_low_confidence,
    is_name_lock_active
)
from discord_bot.core.engines.confirm_flow import (
    build_soft_confirm_payload,
    build_disambiguation_payload,
    apply_user_corrections,
    build_name_change_prompt
)
```

### 2. Modify `submit_ranking` Command Flow

**Current flow**:
```
1. Validate inputs (stage, day, screenshot)
2. Parse screenshot → RankingData
3. Check duplicate
4. Save to storage
5. Send success embed
```

**New flow with validation**:
```
1. Validate inputs (stage, day, screenshot)
2. Parse screenshot → parsed dict
3. Fetch cached player profile
4. Calculate confidence scores
5. Apply cached values if confidence low
6. Sanitize and validate
7. BRANCH ON CONFIDENCE:
   a) >= 0.99: Auto-accept → save
   b) 0.95-0.989: Soft confirm → wait for button
   c) < 0.95: Disambiguation → wait for modal/button
8. After confirmation: save to storage
9. Update player profile cache
10. Send success embed
```

### 3. Exact Code Location

**File**: `discord_bot/cogs/ranking_cog.py`

**Function**: `async def submit_ranking()`

**Insert AFTER** screenshot parsing (around line 280-300):

```python
# EXISTING CODE:
parsed = await self.processor.parse_ranking_screenshot(
    image_data, user_id, interaction.user.name, guild_id, event_week
)

if not parsed:
    await interaction.response.send_message(
        "❌ Could not parse screenshot...",
        ephemeral=True
    )
    return

# ═══════════════════════════════════════════════════════
# NEW CODE: R8 VALIDATION LAYER
# ═══════════════════════════════════════════════════════

# Step 1: Fetch cached player profile
conn = self.storage._get_connection()
cached_profile = get_player(conn, user_id)

# Step 2: Calculate confidence scores
raw_text = parsed.get('_raw_text', '')  # Assume processor includes this
ui_flags = parsed.get('_ui_flags', {})

confidence_map = {
    'score': score_confidence(raw_text, parsed['score']),
    'phase': phase_confidence(ui_flags),
    'day': day_confidence(ui_flags),
    'server_id': server_confidence(raw_text)[1],
    'guild': guild_confidence(raw_text, cached_profile.get('guild') if cached_profile else None)[1],
    'player_name': name_confidence(raw_text, cached_profile.get('player_name') if cached_profile else None)[1]
}

overall_conf = overall_confidence(confidence_map)
confidence_map['overall'] = overall_conf

# Step 3: Apply cached values when confidence is low
parsed = prefer_cached_when_low_confidence(parsed, cached_profile, confidence_map)

# Step 4: Sanitize and validate
is_valid, errors = sanitize_and_validate(parsed)
if not is_valid:
    error_text = '\n'.join(f"• {err}" for err in errors)
    await interaction.response.send_message(
        f"❌ Validation failed:\n{error_text}",
        ephemeral=True
    )
    return

# Step 5: Branch on confidence level
if overall_conf >= 0.99:
    # AUTO-ACCEPT: High confidence, proceed directly
    await interaction.response.defer(ephemeral=False)
    # Continue to save logic below...
    
elif overall_conf >= 0.95:
    # SOFT CONFIRM: Show confirmation button
    payload = build_soft_confirm_payload(parsed, confidence_map)
    
    # Send ephemeral message with confirmation view
    view = SoftConfirmView(parsed, self, timeout=120)
    embed = discord.Embed.from_dict(payload['embed'])
    
    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )
    return  # Wait for button interaction
    
else:
    # DISAMBIGUATION: Show correction modal/buttons
    payload = build_disambiguation_payload(parsed, {}, confidence_map)
    
    view = LowConfidenceView(parsed, self, timeout=120)
    embed = discord.Embed.from_dict(payload['embed'])
    
    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )
    return  # Wait for modal/button interaction

# ═══════════════════════════════════════════════════════
# CONTINUE WITH EXISTING SAVE LOGIC (for auto-accept path)
# ═══════════════════════════════════════════════════════

# Build RankingData object
ranking = RankingData(
    user_id=user_id,
    username=interaction.user.name,
    guild_tag=parsed['guild'],
    event_week=event_week,
    phase=parsed['phase'],
    day=parsed['day'],
    category=...,  # Existing logic
    rank=parsed.get('rank', 0),
    score=parsed['score'],
    player_name=parsed['player_name'],
    submitted_at=datetime.utcnow(),
    screenshot_url=screenshot.url,
    guild_id=guild_id,
    kvk_run_id=kvk_run.id
)

# Save with overwrite logic
ranking_id, was_updated, score_changed = self.storage.save_or_update_ranking(
    ranking, kvk_run_id=kvk_run.id
)

# Update player profile cache
upsert_player(
    conn,
    user_id,
    parsed['server_id'],
    parsed['guild'],
    parsed['player_name']
)

# Send success embed (existing logic)
# ...
```

### 4. Add View Classes at Bottom of File

**Location**: End of `discord_bot/cogs/ranking_cog.py`, before `async def setup()`

```python
class SoftConfirmView(discord.ui.View):
    """View for soft confirmation (95-99% confidence)."""
    
    def __init__(self, parsed: Dict[str, Any], cog: 'RankingCog', timeout: int = 120):
        super().__init__(timeout=timeout)
        self.parsed = parsed
        self.cog = cog
        self.value = None
    
    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.success, custom_id='confirm')
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'confirm'
        self.stop()
        
        # Continue with save logic
        await interaction.response.defer(ephemeral=False)
        # Call cog._finalize_ranking_save(interaction, self.parsed)
        # TODO: Extract save logic to helper method
    
    @discord.ui.button(label='Edit', style=discord.ButtonStyle.secondary, custom_id='edit')
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'edit'
        self.stop()
        
        # Show correction modal
        modal = CorrectionModal(self.parsed)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, custom_id='cancel')
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'cancel'
        self.stop()
        
        await interaction.response.send_message(
            "❌ Submission cancelled.",
            ephemeral=True
        )


class LowConfidenceView(discord.ui.View):
    """View for disambiguation (<95% confidence)."""
    
    def __init__(self, parsed: Dict[str, Any], cog: 'RankingCog', timeout: int = 120):
        super().__init__(timeout=timeout)
        self.parsed = parsed
        self.cog = cog
        self.value = None
    
    @discord.ui.button(label='Edit Values', style=discord.ButtonStyle.primary, custom_id='edit')
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'edit'
        self.stop()
        
        modal = CorrectionModal(self.parsed)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Use As-Is', style=discord.ButtonStyle.secondary, custom_id='accept')
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'accept'
        self.stop()
        
        # Continue with save despite low confidence
        await interaction.response.defer(ephemeral=False)
        # Call cog._finalize_ranking_save(interaction, self.parsed)
    
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, custom_id='cancel')
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'cancel'
        self.stop()
        
        await interaction.response.send_message(
            "❌ Submission cancelled.",
            ephemeral=True
        )


class CorrectionModal(discord.ui.Modal, title='Correct Ranking Data'):
    """Modal for manual correction of uncertain fields."""
    
    def __init__(self, parsed: Dict[str, Any]):
        super().__init__()
        self.parsed = parsed
        
        # Add input fields with prefill
        self.guild_input = discord.ui.TextInput(
            label='Guild Tag',
            placeholder='e.g., TAO',
            default=parsed.get('guild', ''),
            required=True,
            max_length=6
        )
        self.add_item(self.guild_input)
        
        self.name_input = discord.ui.TextInput(
            label='Player Name',
            placeholder='Your in-game name',
            default=parsed.get('player_name', ''),
            required=True,
            max_length=30
        )
        self.add_item(self.name_input)
        
        self.score_input = discord.ui.TextInput(
            label='Score (numbers only)',
            placeholder='e.g., 1250000',
            default=str(parsed.get('score', '')),
            required=True,
            max_length=15
        )
        self.add_item(self.score_input)
        
        self.server_input = discord.ui.TextInput(
            label='Server ID',
            placeholder='e.g., 10435',
            default=str(parsed.get('server_id', '')),
            required=False,
            max_length=6
        )
        self.add_item(self.server_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Apply corrections
        user_input = {
            'guild': self.guild_input.value,
            'player_name': self.name_input.value,
            'score': self.score_input.value,
            'server_id': self.server_input.value
        }
        
        corrected = apply_user_corrections(self.parsed, user_input)
        
        # Validate corrected data
        is_valid, errors = sanitize_and_validate(corrected)
        if not is_valid:
            error_text = '\n'.join(f"• {err}" for err in errors)
            await interaction.response.send_message(
                f"❌ Invalid input:\n{error_text}",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=False)
        # TODO: Call cog._finalize_ranking_save(interaction, corrected)
```

### 5. Helper Method for Save Logic

Add to `RankingCog` class:

```python
async def _finalize_ranking_save(
    self,
    interaction: discord.Interaction,
    parsed: Dict[str, Any]
) -> None:
    """
    Final save logic after confirmation.
    
    Extracted to avoid duplication between auto-accept and manual confirm paths.
    """
    # Get KVK run and event info
    kvk_run = await self.kvk_tracker.ensure_run(...)  # Existing logic
    event_week = self._format_event_week_label(kvk_run)
    
    # Build RankingData
    ranking = RankingData(
        user_id=str(interaction.user.id),
        username=interaction.user.name,
        guild_tag=parsed['guild'],
        event_week=event_week,
        phase=parsed['phase'],
        day=parsed['day'],
        category=self._determine_category(parsed['phase'], parsed['day']),
        rank=parsed.get('rank', 0),
        score=parsed['score'],
        player_name=parsed['player_name'],
        submitted_at=datetime.utcnow(),
        screenshot_url=parsed.get('_screenshot_url'),
        guild_id=str(interaction.guild_id),
        kvk_run_id=kvk_run.id
    )
    
    # Save with overwrite logic
    conn = self.storage._get_connection()
    ranking_id, was_updated, score_changed = self.storage.save_or_update_ranking(
        ranking, kvk_run_id=kvk_run.id
    )
    
    # Update player profile cache
    lock_updates = None
    if parsed.get('_user_corrected_name'):
        # User manually confirmed name change, lock for 24h
        from datetime import timedelta
        locked_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        lock_updates = {
            'name_locked': True,
            'name_locked_until': locked_until
        }
    
    upsert_player(
        conn,
        str(interaction.user.id),
        parsed['server_id'],
        parsed['guild'],
        parsed['player_name'],
        lock_updates=lock_updates
    )
    
    # Build success embed
    if parsed['phase'] == 'prep' and parsed['day'] == 'overall':
        embed = self._build_prep_overall_success_embed(...)
    elif parsed['phase'] == 'prep':
        embed = self._build_prep_day_success_embed(...)
    else:
        embed = self._build_war_success_embed(...)
    
    await interaction.followup.send(embed=embed, ephemeral=False)
```

## Summary

1. **Import validation modules** at top of ranking_cog.py
2. **Modify submit_ranking** to branch on confidence
3. **Add View classes** for confirmation UI
4. **Add CorrectionModal** for manual edits
5. **Extract _finalize_ranking_save** helper to avoid duplication
6. **Update player profile** after every successful save

This maintains backward compatibility while adding the validation layer as a middleware step.
