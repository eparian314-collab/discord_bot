🦛 HippoBot — A Multilingual Discord Companion
🌍 Helping friends connect across languages through games, translation, and fun.

About This Project

This is the first project to ever make it out of my laptop.
I’ve been coding for almost six years — mostly self-taught — and took two years of community college computer science courses to strengthen my foundation.

The idea for this project came from a strategy game I play with international friends. I wanted a way for us to communicate better, stay active as a guild, and share daily interactions — even when we didn’t all speak the same language.

I’ve always admired Discord bots that could track rankings or post statistics, so I decided to create my own bot that focuses on translation and engagement. What started as a simple experiment turned into something much bigger.

Development Journey

This project went through many renditions.
I worked on it tirelessly for almost a month, constantly refining how the bot handled messages, roles, and translations.

The first version was simple — just a logic tree on paper and some research into free APIs. Google Translate was my starting point because it covered the widest range of languages.

From there, I designed the translation flow:

<source_text> + <language_code> → <target_language>

I think the years of doing small projects and studying basics through YouTube and other sources helped me build on these three concepts a lot. With the source text, I wondered how my bot could know what the source language is — and what to do with similar words that can mean different things.

We had a translator bot that sometimes misfired when people used short words like “yeah” or “ya,” translating them into a completely different language. That made me realize I could add more data and build helpers and functions to expand how well the bot understands language.

Then I found out Google Translate was pretty inconsistent, so I researched more and decided to implement a three-tier translation protocol, combining multiple APIs and incorporating AI with a custom word list to give my project more personality.

I had a lot of fun building this and letting my curiosity flow. I also learned about debugging, file structures, and the trade-offs between a smaller, direct project and connecting what could feel like multiple bots into one animated helper.

Then came the fun part — connecting languages to emoji roles in Discord.
I built a giant language map file that matched each language’s code to its flag emoji, so users could choose their preferred language by reacting with a flag.

Eventually, I noticed that certain flags (like the Filipino 🇵🇭 flag) needed special handling for additional dialects and codes — that challenge helped me understand how deep localization systems can go.

Throughout the days and nights I spent designing this project, I kept finding more things I wanted to improve — making the experience more seamless and user-friendly. I wanted the bot to really understand what users meant, handle edge cases gracefully, and feel alive.

It became like a baby to me — currently being tested, refined, and operated by my guild. The gem of this project is truly the language processor. I wanted to see how refined I could make a translation bot with the tools available today.

This project is my testament to curiosity — a deep dive down the rabbit hole. I wanted to create something that felt personal, unique, and meaningful.

I’ve been afraid to take this step for a long time, but this is the first of many projects. I hope to eventually break off the additional game features and leave just the language and translation system so others can use it in their own fun projects.

Architecture

HippoBot is powered by a modular engine system that separates:

• Translation Logic — DeepL → MyMemory → Google Translate (in order of priority)
• Game Engine — Handles cookies, stats, and Pokémon-style battles
• Storage Engine — Keeps track of user language preferences, scores, and roles
• Error and Cache Managers — Ensure stability and performance

Lessons Learned

I learned a lot about:

• Building modular Python systems and avoiding circular imports
• Designing async pipelines for Discord bots
• Handling API fallbacks and caching
• Structuring large-scale personal projects
• Staying patient through hundreds of small fixes

Future Plans

• Refactor the Pokémon mini-game and improve storage communication
• Add better multilingual support (top five broadcast languages)
• Create a dashboard interface to monitor translation activity
• Continue refining the translation engines for speed and accuracy

Final Thoughts

This project taught me more than any class could.
It represents years of curiosity, trial and error, and persistence.

I don’t think I’ll ever stop coding — so follow HippoBot’s journey as it evolves over the years.
