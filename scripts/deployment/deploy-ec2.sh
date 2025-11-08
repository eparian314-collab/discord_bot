#!/bin/bash
set -e

echo "🚀 Deploying HippoBot to EC2..."
echo "=" | head -c 50

# Step 1: Delete old files
echo "1️⃣  Removing old project files and environment..."
rm -rf ~/discord_bot
rm -rf ~/.venv
echo "✅ Old files removed"

# Step 2: Clone new branch
echo ""
echo "2️⃣  Cloning new branch from GitHub..."
git clone -b command-sync-fix https://github.com/eparian314-collab/discord_bot.git ~/discord_bot
cd ~/discord_bot
echo "✅ Repository cloned"

# Step 3: Create virtual environment
echo ""
echo "3️⃣  Creating Python virtual environment..."
python3 -m venv ~/.venv
source ~/.venv/bin/activate
echo "✅ Virtual environment created"

# Step 4: Install dependencies
echo ""
echo "4️⃣  Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Step 5: Set up .env file
echo ""
echo "5️⃣  Setting up .env file..."
if [ -f .env.example ]; then
    cp .env.example .env
    echo "⚠️  .env created from .env.example - you need to edit it with your secrets!"
    echo "📝 Edit with: nano .env"
else
    echo "⚠️  No .env.example found - create .env manually"
fi
echo "✅ .env file ready"

# Step 6: Run database migrations
echo ""
echo "6️⃣  Running database migrations..."
python discord_bot/scripts/migrations/fix_pokemon_schema.py
echo "✅ Database migrations completed"

# Step 7: Sync commands (optional - requires bot running)
echo ""
echo "7️⃣  Bot is ready to start!"
echo "🎮 To start the bot, run:"
echo "   source ~/.venv/bin/activate"
echo "   cd ~/discord_bot"
echo "   python main.py"
echo ""
echo "✨ Deployment complete!"
