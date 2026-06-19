"""Seed data for competitors and mock competitor content."""

COMPETITORS_SEED = [
    {
        "name": "IGP Business",
        "handles": {
            "website": "https://www.igp.com/corporate-gifts",
            "linkedin": "https://www.linkedin.com/company/igpcom/",
            "instagram": "https://www.instagram.com/igp_com/",
            "facebook": "https://www.facebook.com/IGPcom/",
        },
    },
    {
        "name": "FNP Corporate",
        "handles": {
            "website": "https://www.fnp.com/corporate-gifts",
            "linkedin": "https://www.linkedin.com/company/fnp-world/",
            "instagram": "https://www.instagram.com/fnp_com/",
            "facebook": "https://www.facebook.com/fnpdotcom/",
        },
    },
    {
        "name": "Giftana",
        "handles": {
            "website": "https://www.giftanaindia.com",
            "linkedin": "https://www.linkedin.com/company/giftana/",
            "instagram": "https://www.instagram.com/giftanaindia/",
            "facebook": "https://www.facebook.com/giftanaindia/",
        },
    },
    {
        "name": "OffiStore India",
        "handles": {
            "website": "https://www.offistore.in",
            "linkedin": "https://www.linkedin.com/company/offistoreindia/",
            "instagram": "https://www.instagram.com/offistoreindia/",
            "facebook": "https://www.facebook.com/offistoreindia/",
        },
    },
    {
        "name": "Across Corporate",
        "handles": {
            "website": "https://www.acrosscorporate.com",
            "linkedin": "https://www.linkedin.com/company/across-corporate/",
            "instagram": "https://www.instagram.com/acrosscorporate/",
            "facebook": "https://www.facebook.com/acrosscorporate/",
        },
    },
    {
        "name": "Saffron India",
        "handles": {
            "website": "https://www.saffronindia.com",
            "linkedin": "https://www.linkedin.com/company/saffron-india/",
            "instagram": "https://www.instagram.com/saffronindia/",
            "facebook": "https://www.facebook.com/saffronindia/",
        },
    },
    {
        "name": "Pinnacle Gifting",
        "handles": {
            "website": "https://www.pinnaclegifting.com",
            "linkedin": "https://www.linkedin.com/company/pinnacle-gifting-official/",
            "instagram": "https://www.instagram.com/pinnacle.gifting_official/",
            "facebook": "https://www.facebook.com/pinnaclegiftingofficial/",
        },
    },
    {
        "name": "Consortium Gifts",
        "handles": {
            "website": "https://www.consortiumgifts.com",
            "linkedin": "https://www.linkedin.com/company/consortium-gifts/",
            "instagram": "https://www.instagram.com/consortiumgifts/",
            "facebook": "https://www.facebook.com/consortiumgifts/",
        },
    },
    {
        "name": "Giftcart Corporate",
        "handles": {
            "website": "https://www.giftcart.com/corporate-gifts",
            "linkedin": "https://www.linkedin.com/company/giftcart/",
            "instagram": "https://www.instagram.com/giftcart/",
            "facebook": "https://www.facebook.com/giftcart/",
        },
    },
    {
        "name": "PrintStop Corporate Gifting",
        "handles": {
            "website": "https://www.printstop.co.in/corporate-gifting",
            "linkedin": "https://www.linkedin.com/company/printstop-india/",
            "instagram": "https://www.instagram.com/printstopindia/",
            "facebook": "https://www.facebook.com/printstopindia/",
        },
    },
]


# Realistic mock competitor posts (caption + hook + format + engagement)
MOCK_COMPETITOR_POSTS = [
    {
        "platform": "instagram",
        "caption": "Stop scrolling. Your team's Diwali gift just got upgraded. Premium hampers from ₹999 — branded, personalised, delivered pan-India.",
        "hook": "Stop scrolling.",
        "format": "carousel",
        "hashtags": ["#corporategifting", "#diwaligifts", "#employeegifting"],
        "likes": 1840, "comments": 92,
        "theme": "festive corporate gifting",
    },
    {
        "platform": "instagram",
        "caption": "5 gifting mistakes that kill employee morale (#3 will surprise you). Save this for your next review cycle 👇",
        "hook": "5 gifting mistakes that kill employee morale",
        "format": "carousel",
        "hashtags": ["#hrtips", "#employeeengagement", "#corporategifts"],
        "likes": 2350, "comments": 178,
        "theme": "HR education",
    },
    {
        "platform": "linkedin",
        "caption": "We shipped 12,000 onboarding kits in 9 days. Here's the operations playbook we used — sharing it free because too many founders are flying blind on gifting logistics.",
        "hook": "We shipped 12,000 onboarding kits in 9 days.",
        "format": "single_image",
        "hashtags": ["#operations", "#d2c", "#founderstory"],
        "likes": 1120, "comments": 86,
        "theme": "founder ops storytelling",
    },
    {
        "platform": "instagram",
        "caption": "POV: it's Monday morning and you remembered your team's anniversary is tomorrow. Don't panic — 24h delivery available.",
        "hook": "POV: it's Monday morning",
        "format": "single_image",
        "hashtags": ["#mondaymotivation", "#lastminutegifts"],
        "likes": 980, "comments": 41,
        "theme": "POV trending hook",
    },
    {
        "platform": "facebook",
        "caption": "Real talk: most corporate gifts end up in a drawer. Here's how we design ones people actually use — and remember.",
        "hook": "Real talk:",
        "format": "single_image",
        "hashtags": ["#corporategifting"],
        "likes": 670, "comments": 38,
        "theme": "honest take",
    },
    {
        "platform": "instagram",
        "caption": "This ₹499 desk organizer has a 4.8★ rating across 12,000 reviews. Bulk-order it for your office before stock runs out.",
        "hook": "This ₹499 desk organizer",
        "format": "single_image",
        "hashtags": ["#officeessentials", "#desksetup"],
        "likes": 1450, "comments": 67,
        "theme": "social proof + product",
    },
    {
        "platform": "linkedin",
        "caption": "Building a D2C brand in India: 7 lessons I wish someone told me before I burned ₹40L on the wrong things.",
        "hook": "Building a D2C brand in India: 7 lessons",
        "format": "carousel",
        "hashtags": ["#d2cindia", "#founderlessons", "#startup"],
        "likes": 2240, "comments": 312,
        "theme": "founder lessons",
    },
    {
        "platform": "instagram",
        "caption": "Things I wish I knew before starting my kitchen-gadget collection. Thread 👇",
        "hook": "Things I wish I knew",
        "format": "carousel",
        "hashtags": ["#kitchenhacks", "#kitchengadgets"],
        "likes": 1980, "comments": 134,
        "theme": "tips listicle",
    },
    {
        "platform": "facebook",
        "caption": "Gift idea for your remote team: a cozy desk-setup hamper that says 'we see you'. From ₹1499 per kit.",
        "hook": "Gift idea for your remote team",
        "format": "single_image",
        "hashtags": ["#remotework", "#teamculture"],
        "likes": 540, "comments": 22,
        "theme": "remote team gifting",
    },
    {
        "platform": "instagram",
        "caption": "Tested: 8 viral kitchen gadgets — only 3 are actually worth your money. Swipe to see which ones made the cut.",
        "hook": "Tested: 8 viral kitchen gadgets",
        "format": "carousel",
        "hashtags": ["#kitchengadgets", "#producttest"],
        "likes": 3120, "comments": 245,
        "theme": "honest review",
    },
    {
        "platform": "linkedin",
        "caption": "Our biggest corporate client almost left us last quarter. Here's the painful feedback that made us redesign our entire onboarding kit experience.",
        "hook": "Our biggest corporate client almost left us",
        "format": "single_image",
        "hashtags": ["#b2b", "#clientsuccess"],
        "likes": 890, "comments": 64,
        "theme": "vulnerability + lesson",
    },
    {
        "platform": "instagram",
        "caption": "Trend alert: 'desk dopamine' is the new productivity hack. Here are 5 small upgrades under ₹999 that genuinely change how you feel about your workspace.",
        "hook": "Trend alert: 'desk dopamine'",
        "format": "carousel",
        "hashtags": ["#deskdecor", "#productivity"],
        "likes": 1690, "comments": 88,
        "theme": "trend-jacking",
    },
]
