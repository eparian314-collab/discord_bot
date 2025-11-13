# Personality phrase stubs for LanguageBot
import random

KNOWN_FRIENDS = [
    "Zee", "Jesus", "Lord Tree", "Jager", "Fookit", "Stick", "Dan", "Mars", "Mazier", "Gooner", "Muya", "Ace"
]

PERSONALITY_PHRASES = {
    "friendly": [
        "Hey there, {friend}! How can I help you today?",
        "{friend}, hope you're having a great day!",
        "What's up, {friend}? Need anything?",
        "Always happy to see you, {friend}!"
    ],
    "serious": [
        "{friend}, please provide your request.",
        "Processing your query, {friend}.",
        "Awaiting instructions, {friend}.",
        "Your request is being handled, {friend}."
    ],
    "playful": [
        "Ready to roll, {friend}! Let's have some fun!",
        "{friend}, are you prepared for some madness?",
        "Let's get wild, {friend}!",
        "{friend}, time for a little chaos!"
    ],
    "madlibs": [
        "{friend} just {verb} the {noun}!",
        "Watch out, {friend} is about to {verb} a {noun}!",
        "Did you see {friend} {verb} with a {noun}?",
        "{friend} and the {noun} went to {place} to {verb}!"
    ]
}

MADLIBS_VERBS = ["conquered", "befriended", "danced with", "challenged", "painted", "tickled", "outsmarted", "hugged"]
MADLIBS_NOUNS = ["dragon", "robot", "banana", "wizard", "goblin", "spaceship", "cookie", "unicorn"]
MADLIBS_PLACES = ["the moon", "the jungle", "the disco", "the library", "the secret lair", "the beach"]
MADLIBS_ACTIONS = ["jumped over", "sang to", "built", "destroyed", "coded", "explored", "discovered", "hid from"]
MADLIBS_GREETINGS = ["Yo", "Sup", "Hello", "Greetings", "Hey", "Ahoy", "Hola", "Bonjour"]
MADLIBS_OBJECTS = ["castle", "computer", "sandwich", "spaceship", "book", "mountain", "puzzle", "painting"]
MADLIBS_EMOTIONS = ["happy", "confused", "excited", "bored", "curious", "angry", "silly", "proud"]

PERSONALITY_PHRASES["madlibs"] += [
    "{greeting}, {friend}! Today you are feeling {emotion}.",
    "{friend} just {action} a {object} at {place}!",
    "Rumor has it {friend} was {emotion} after they {verb} the {noun}.",
    "{friend} and {friend2} {action} together in {place}.",
    "{friend} found a {object} and felt {emotion} about it.",
    "{friend} challenged {friend2} to {verb} a {object} at {place}!",
    "{greeting}, {friend}! You just {action} a {object} at {place} and everyone lost their minds!",
    "Rumor has it {friend} {verb} a {noun} while wearing socks and sandals at {place}.",
    "{friend} and {friend2} tried to {action} a {object} but ended up starting a dance-off in {place}.",
    "Breaking news: {friend} was caught {verb} with a {noun} in {place}—again!",
    "{friend} found a {object} and felt {emotion} about it, then told {friend2} who just shrugged.",
    "{friend} challenged {friend2} to {verb} a {object} at {place}, loser buys pizza!",
    "Last night, {friend} {action} a {object} and now the group chat will never recover.",
    "{friend} and {friend2} went to {place} to {action} a {object}, but got distracted by memes.",
    "If you see {friend} {verb} a {noun} in {place}, just act normal. It's Tuesday.",
    "{greeting}! {friend} is feeling {emotion} and plotting to {action} a {object} at {place}.",
]


def get_madlib_phrase():
    friend = random.choice(KNOWN_FRIENDS)
    friend2 = random.choice([f for f in KNOWN_FRIENDS if f != friend])
    verb = random.choice(MADLIBS_VERBS)
    noun = random.choice(MADLIBS_NOUNS)
    place = random.choice(MADLIBS_PLACES)
    action = random.choice(MADLIBS_ACTIONS)
    greeting = random.choice(MADLIBS_GREETINGS)
    object_ = random.choice(MADLIBS_OBJECTS)
    emotion = random.choice(MADLIBS_EMOTIONS)
    templates = PERSONALITY_PHRASES["madlibs"]
    template = random.choice(templates)
    return template.format(
        friend=friend,
        friend2=friend2,
        verb=verb,
        noun=noun,
        place=place,
        action=action,
        greeting=greeting,
        object=object_,
        emotion=emotion
    )
