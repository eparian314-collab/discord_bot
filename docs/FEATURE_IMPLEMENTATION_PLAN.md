# Feature Implementation Plan
## Comprehensive Bot Enhancement Specification

### Overview
This document outlines 8 major feature enhancements to the Discord bot system.

---

## 1. Slash Command UI Optimization

### Goal
Improve command discoverability by ensuring "add" and "remove" actions appear first in autocomplete lists.

### Changes Required
**File: `cogs/role_management_cog.py`**
- Rename `assign` → `add` 
- Rename `remove` → `remove` (already starts with 'r', good)
- Keep `list` as is

**Benefit:** When users type `/language add`, they immediately see the add command without scrolling.

---

## 2. Natural Mood Degradation

### Goal
Bot mood should decay over time if not refreshed by interactions, making the bot more dynamic and realistic.

### Implementation
**File: `core/engines/personality_engine.py`**

```python
# Add to PersonalityEngine class:

async def get_mood_with_decay(self, user_id: int, guild_id: int) -> str:
    """Get user mood with time-based degradation applied."""
    current_mood = await self.get_mood(user_id, guild_id)
    last_interaction = await self._get_last_interaction_time(user_id, guild_id)
    
    if not last_interaction:
        return current_mood
    
    # Calculate decay based on time elapsed
    hours_elapsed = (datetime.now() - last_interaction).total_seconds() / 3600
    
    # Decay rates:
    # - Happy: decays to neutral after 24 hours
    # - Excited: decays to happy after 12 hours  
    # - Grumpy: decays to neutral after 48 hours
    # - Neutral: no decay
    
    decay_map = {
        ('excited', 12): 'happy',
        ('happy', 24): 'neutral',
        ('grumpy', 48): 'neutral'
    }
    
    for (mood, hours), target_mood in decay_map.items():
        if current_mood == mood and hours_elapsed >= hours:
            await self.set_mood(user_id, guild_id, target_mood)
            return target_mood
    
    return current_mood
```

**Database Schema Addition:**
```sql
-- Add to user_profiles table
ALTER TABLE user_profiles ADD COLUMN last_mood_interaction DATETIME;
```

---

## 3. Relationship Degradation

### Goal
User relationships with the bot should decay if they don't interact, encouraging regular engagement.

### Implementation
**File: `core/engines/relationship_manager.py` (if exists) or create new**

```python
class RelationshipManager:
    """Manages user-bot relationships with time-based decay."""
    
    DECAY_RATES = {
        'stranger': 0,  # Can't go lower
        'acquaintance': 7 * 24,  # 7 days → stranger
        'friend': 14 * 24,  # 14 days → acquaintance
        'close_friend': 30 * 24,  # 30 days → friend
        'best_friend': 60 * 24  # 60 days → close_friend
    }
    
    async def get_relationship_with_decay(self, user_id: int, guild_id: int) -> str:
        """Get relationship level with decay applied."""
        current_level = await self._get_relationship_level(user_id, guild_id)
        last_interaction = await self._get_last_relationship_interaction(user_id, guild_id)
        
        if not last_interaction:
            return 'stranger'
        
        hours_elapsed = (datetime.now() - last_interaction).total_seconds() / 3600
        
        # Apply decay
        relationship_order = ['stranger', 'acquaintance', 'friend', 'close_friend', 'best_friend']
        current_index = relationship_order.index(current_level)
        
        for i in range(current_index, 0, -1):
            level = relationship_order[i]
            decay_hours = self.DECAY_RATES[level]
            if hours_elapsed >= decay_hours:
                new_level = relationship_order[i - 1]
                await self._set_relationship_level(user_id, guild_id, new_level)
                return new_level
        
        return current_level
```

**Database Schema Addition:**
```sql
CREATE TABLE IF NOT EXISTS user_relationships (
    user_id TEXT,
    guild_id TEXT,
    relationship_level TEXT DEFAULT 'stranger',
    last_interaction DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_interactions INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
);
```

---

## 4. Consolidated Easter Egg Command

### Goal
Replace multiple easter egg commands (rps, joke, catfact, weather, 8ball) with a single `/easteregg` command that shows a selection menu.

### Implementation
**File: `cogs/easteregg_cog.py`**

```python
class EasterEggSelect(discord.ui.Select):
    """Dropdown menu for easter egg selection."""
    
    def __init__(self):
        options = [
            discord.SelectOption(label="🎲 Rock Paper Scissors", value="rps", description="Play RPS with Baby Hippo"),
            discord.SelectOption(label="😂 Random Joke", value="joke", description="Get a funny joke"),
            discord.SelectOption(label="🐱 Cat Fact", value="catfact", description="Learn about cats"),
            discord.SelectOption(label="🌤️ Weather", value="weather", description="Check the weather"),
            discord.SelectOption(label="🎱 Magic 8-Ball", value="8ball", description="Ask a yes/no question"),
        ]
        super().__init__(placeholder="Choose an easter egg...", options=options, min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        # Check daily limit (5 eggs per day)
        usage_count = await self.cog.check_daily_usage(interaction.user.id)
        if usage_count >= 5:
            await interaction.response.send_message(
                "🦛 You've used all 5 easter eggs today! Come back tomorrow for more fun! 🎉",
                ephemeral=True
            )
            return
        
        # Execute selected easter egg
        selected = self.values[0]
        await self.cog.execute_easteregg(interaction, selected)
        
        # Track usage
        await self.cog.increment_daily_usage(interaction.user.id)

@app_commands.command(name="easteregg", description="Choose an easter egg surprise!")
async def easteregg(self, interaction: discord.Interaction):
    view = discord.ui.View()
    view.add_item(EasterEggSelect())
    await interaction.response.send_message("🦛 Pick your easter egg:", view=view, ephemeral=True)
```

**Remove old commands:**
- `/rps` → moved to easter egg menu
- `/joke` → moved to easter egg menu
- `/catfact` → moved to easter egg menu
- `/weather` → moved to easter egg menu  
- `/8ball` → moved to easter egg menu

---

## 5. Easter Egg Daily Limits

### Goal
Users can only activate 5 easter eggs per day to prevent spam and maintain engagement.

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS easteregg_usage (
    user_id TEXT,
    date TEXT,  -- Format: YYYY-MM-DD
    usage_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);
```

### Implementation
```python
async def check_daily_usage(self, user_id: int) -> int:
    """Check how many easter eggs user has used today."""
    today = datetime.now().strftime('%Y-%m-%d')
    result = await self.db.execute(
        "SELECT usage_count FROM easteregg_usage WHERE user_id = ? AND date = ?",
        (str(user_id), today)
    )
    row = await result.fetchone()
    return row[0] if row else 0

async def increment_daily_usage(self, user_id: int):
    """Increment user's daily easter egg usage."""
    today = datetime.now().strftime('%Y-%m-%d')
    await self.db.execute(
        "INSERT INTO easteregg_usage (user_id, date, usage_count) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id, date) DO UPDATE SET usage_count = usage_count + 1",
        (str(user_id), today)
    )
    await self.db.commit()
```

---

## 6. Admin Cookie System

### Goal
Admins get 2 cookies per day:
- 1 cookie for themselves
- 1 cookie to gift to another user (not server master or another admin)

### Implementation
**File: `cogs/admin_cog.py` or `cogs/game_cog.py`**

```python
@app_commands.command(name="admin_cookie", description="Admin: Claim your daily cookie or gift one")
@app_commands.describe(
    action="'claim' for yourself or 'gift' to give to someone",
    target="User to gift cookie to (only for 'gift' action)"
)
async def admin_cookie(
    self, 
    interaction: discord.Interaction,
    action: Literal["claim", "gift"],
    target: Optional[discord.Member] = None
):
    # Check if user is admin or helper role
    is_admin = await self._is_admin(interaction.user, interaction.guild)
    is_helper = await self._has_helper_role(interaction.user, interaction.guild)
    
    if not (is_admin or is_helper):
        await interaction.response.send_message(
            "❌ Only admins and server helpers can use this command.",
            ephemeral=True
        )
        return
    
    if action == "claim":
        # Give cookie to self
        success = await self._give_admin_cookie(interaction.user.id, source="admin_self")
        if success:
            await interaction.response.send_message("🍪 You claimed your admin cookie!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You already claimed your cookie today!", ephemeral=True)
    
    elif action == "gift":
        if not target:
            await interaction.response.send_message("❌ You must specify a user to gift to!", ephemeral=True)
            return
        
        # Check target isn't server master or admin/helper
        if await self._is_owner(target):
            await interaction.response.send_message("❌ Can't gift to the server master!", ephemeral=True)
            return
        
        if await self._is_admin(target, interaction.guild) or await self._has_helper_role(target, interaction.guild):
            await interaction.response.send_message("❌ Can't gift to other admins/helpers!", ephemeral=True)
            return
        
        # Give gift cookie
        success = await self._give_admin_cookie(
            target.id,
            source=f"admin_gift_{interaction.user.id}",
            gifter_id=interaction.user.id
        )
        
        if success:
            await interaction.response.send_message(
                f"🎁 You gifted a cookie to {target.mention}!",
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                "❌ You already gifted your cookie today!",
                ephemeral=True
            )
```

---

## 7. Server Helper Role Configuration

### Goal
Add a `HELPER_ROLE_ID` to config that gives users the same cookie benefits as admins.

### Config Addition (Already Done Above)
```json
{
  "HELPER_ROLE_ID": "222222222222222222"
}
```

### Helper Check Function
```python
async def _has_helper_role(self, user: discord.Member, guild: discord.Guild) -> bool:
    """Check if user has the configured helper role."""
    helper_role_id = os.getenv("HELPER_ROLE_ID")
    if not helper_role_id:
        return False
    
    try:
        role_id = int(helper_role_id)
        return any(role.id == role_id for role in user.roles)
    except (ValueError, TypeError):
        return False
```

---

## 8. Cookie Gift Tracking

### Goal
Track all cookies by source: bot-given, admin gift, or helper gift.

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS cookie_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    source TEXT NOT NULL,  -- 'bot', 'admin_self', 'admin_gift', 'helper_self', 'helper_gift'
    gifter_id TEXT,  -- ID of admin/helper who gave the gift (NULL for bot/self)
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    reason TEXT  -- Optional: 'daily', 'game_reward', 'easter_egg', etc.
);

-- Track daily admin/helper cookie usage
CREATE TABLE IF NOT EXISTS admin_cookie_usage (
    user_id TEXT,
    date TEXT,  -- Format: YYYY-MM-DD
    claimed_self BOOLEAN DEFAULT 0,
    gifted_to TEXT,  -- User ID who received the gift (NULL if not gifted yet)
    PRIMARY KEY (user_id, date)
);
```

### Cookie Manager Update
```python
async def give_cookie(
    self,
    user_id: int,
    amount: int = 1,
    source: str = "bot",
    gifter_id: Optional[int] = None,
    reason: Optional[str] = None
) -> bool:
    """
    Give cookies to a user and track the source.
    
    Args:
        user_id: Recipient's Discord ID
        amount: Number of cookies
        source: One of: 'bot', 'admin_self', 'admin_gift', 'helper_self', 'helper_gift'
        gifter_id: ID of the person giving the gift (for admin/helper gifts)
        reason: Optional reason for the transaction
    """
    # Update user's cookie balance
    await self._increment_cookies(user_id, amount)
    
    # Log the transaction
    await self.db.execute(
        "INSERT INTO cookie_transactions (user_id, amount, source, gifter_id, reason) "
        "VALUES (?, ?, ?, ?, ?)",
        (str(user_id), amount, source, str(gifter_id) if gifter_id else None, reason)
    )
    await self.db.commit()
    return True
```

---

## Implementation Priority

1. ✅ **Config Update** - Add HELPER_ROLE_ID (DONE)
2. **Database Schema** - Add all new tables
3. **Command Renaming** - Optimize UX
4. **Easter Egg Consolidation** - Simplify user experience
5. **Easter Egg Limits** - Prevent spam
6. **Cookie System** - Admin/helper functionality
7. **Mood Degradation** - Add realism
8. **Relationship Degradation** - Encourage engagement

---

## Testing Checklist

- [ ] Config loads HELPER_ROLE_ID correctly
- [ ] Database schema migrations run without errors
- [ ] `/language add` appears before other language commands
- [ ] `/easteregg` dropdown shows all 5 options
- [ ] Easter egg daily limit enforced (5 per day)
- [ ] Admin can claim cookie for self
- [ ] Admin can gift cookie (once per day)
- [ ] Helper role has same cookie privileges
- [ ] Cannot gift to server master or other admins/helpers
- [ ] Cookie transactions logged correctly
- [ ] Mood decays after appropriate time periods
- [ ] Relationships decay after appropriate time periods

---

## Files to Modify

1. `config/config.example.json` ✅
2. `core/storage/schema.sql`
3. `cogs/role_management_cog.py`
4. `cogs/easteregg_cog.py`
5. `cogs/game_cog.py` or `cogs/admin_cog.py`
6. `core/engines/personality_engine.py`
7. `core/engines/relationship_manager.py` (may need to create)
8. `core/engines/cookie_manager.py` (may need to create)

---

*Document created: October 27, 2025*
*Status: Ready for implementation*
