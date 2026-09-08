import argparse
import collections
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from semantic_repairs_v120 import REPAIRS as CLEAN_SOURCE_SEMANTIC_REPAIRS
except ModuleNotFoundError:
    CLEAN_SOURCE_SEMANTIC_REPAIRS = {}

try:
    from semantic_repairs_v123 import EXACT as SEMANTIC_EXACT_V123
    from semantic_repairs_v123 import translate_pattern as semantic_v123_translation
except ModuleNotFoundError:
    SEMANTIC_EXACT_V123 = {}

    def semantic_v123_translation(_source):
        return None

FORMAT_TOKEN_RE = re.compile(
    r"\{\[[^\]]+\]\?(?:s|es)?:\}|\\[ntr]|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|"
    r"[A-Za-z][A-Za-z0-9_.-]{0,31})\]|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|%[A-Za-z_][A-Za-z0-9_.-]*%"
)
ENGLISH_RE = re.compile(
    r"(?i)\b(the|and|you|your|with|from|into|must|cannot|available|unavailable|"
    r"default|damage|mastery|characteristics|recommended|rarity|pockets|page|click|level|"
    r"search|current|challenge|item|items|build|resistance|earth|water|fire|air|exact|ones|"
    r"following|remove|purchase|sale|window|offer|remaining|team|are|is|was|were|has|have|"
    r"hidden|color|spell|spells|active|open|chest|ranking|rank|select|close|cancel|confirm|"
    r"yes|no|name|description|price|quantity|inventory|equipment|quest|quests|achievement|"
    r"achievements|reward|rewards|fight|turn|round|target|range|cost|health|armor|critical|"
    r"penalty|locked|unlocked|copy|paste|delete|edit|save|load|next|previous|back|"
    r"calm|again|well|finally|below|above|using|only|when|then|each|every|first|last|"
    r"please|other|more|still|already|together|without|while|during|after|before|"
    r"finished|failed|waiting|support|protection|positioning|mobility|crafting|"
    r"professions|vicinity|fury|resident|outlaw|inactive|harvest|harvests|"
    r"refinement|refinements|component|components|weapon|weapons|sidekick|"
    r"sidekicks|tool|tools|emote|emotes|display|windows|workshop|workshops|"
    r"resource|resources|recipe|recipes|ranching|lumberjack|farmer|fisherman|"
    r"trapper|herbalist|miner|of|for|to|by|this|that|these|those|"
    r"would|could|should|summon|summons|summoned|caster|casters|reduce|"
    r"reduces|reduced|gain|gains|gained|trigger|triggers|triggered|become|becomes|"
    r"became|give|gives|given|inflict|inflicts|inflicted|remove|removes|removed|"
    r"reach|access|key|juice)\b"
)
JOINABLE_ENGLISH_WORDS = {
    "current", "active", "hidden", "color", "spell", "spells", "open",
    "ranking", "select", "default", "damage", "mastery", "level", "item",
    "items", "character", "characteristics", "build", "opening", "linked",
    "water", "fire", "earth", "air", "element", "armor", "resistance",
    "point", "points", "portal", "portals", "monster", "monsters", "turn",
}
ALLOWED_IDENTICAL_WORDS = {
    "bonus", "normal", "portal", "festival", "video", "internet", "arena",
    "robot", "radar", "test", "risk", "plan", "mode", "pixel", "server",
    "forum", "menu", "status", "premium", "stasis", "wakfu", "dofus",
    "kama", "kamas", "pvp", "xp", "ap", "mp", "wp", "metal", "ideal",
    "aura", "tarot", "element", "larva", "beta", "retro", "model", "mineral",
    "totem", "kimono", "platform", "modern", "alarm", "golem", "minimum",
    "bandana", "haven", "mini", "makoffee", "dragoturkey", "toga", "kull",
    "avatar", "miasma", "andalay", "piwi", "rock", "roll", "vegan",
    "flora", "dojo", "hologram", "protein", "anti", "doping", "tank",
    "lorem", "ipsum", "dolor", "amet", "hehehe", "hahaha", "hahahaha", "yippee", "psst",
    "sunnyyyy", "jellivision", "spice", "standard", "hehe", "leap",
    "mutant", "cawwot", "cawwots", "guild", "spam", "biff", "form",
    "world", "abah", "hula", "relic", "naldinho", "flex", "faltom",
    "astral", "dimensional", "eenie", "meenie", "poinkk", "plonk", "rand",
    "postmodern", "funk", "disco", "feng", "shui", "noob", "bowling", "slogan",
    "solo", "salmonella", "mantra",
    # Ters yazılmış laboratuvar günlüğünde Bwork özel adının görünmesi gereken
    # biçimidir; oyuncuya İngilizce düz metin olarak gösterilmez.
    "krowb",
    "panel", "organ", "pilot", "pedal", "diplomat", "program", "disk", "samba", "asteroid",
    "mistral", "film", "patent", "ouroboros", "oolong",
    # Türkçede aynı kullanılan oyun/yerleşik terimler ve WAKFU özel adları.
    "park", "boss", "zaap", "drago",
    "ninja", "hangar", "ferociraptor", "glagla", "plantiguard", "strich",
    # Aksanlı/özel adların Latin harf taramasında kalan parçaları.
    "stle", "clic", "eritif", "lbor",
}
GENERIC_TRANSLATABLE_WORDS = JOINABLE_ENGLISH_WORDS | {
    "today", "tomorrow", "yesterday", "water", "fire", "earth", "air",
    "elemental", "monster", "monsters", "boss", "bosses", "workshop",
    "player", "players", "area", "metal", "guild", "standard", "emote",
    "ultimate", "dimensional", "rift", "craft", "craftsman", "defeat",
    "archmonster", "reward", "rewards", "menu", "profession", "professions",
    "calm", "again", "well", "finally", "only", "when", "then", "each",
    "every", "first", "last", "please", "other", "more", "still", "already",
    "support", "protection", "positioning", "mobility", "crafting", "vicinity",
    "fury", "resident", "outlaw", "inactive", "harvest", "harvests",
    "refinement", "refinements", "component", "components", "weapon",
    "weapons", "sidekick", "sidekicks", "tool", "tools", "emote", "emotes",
    "display", "windows", "workshop",
    "workshops", "resource", "resources", "recipe", "recipes", "ranching",
    "lumberjack", "farmer", "fisherman", "trapper", "herbalist", "miner",
    "of", "for", "to", "by", "this", "that", "these", "those",
    "would", "could", "should", "summon",
    "summons", "summoned", "caster", "casters", "reduce", "reduces",
    "reduced", "gain", "gains", "gained", "trigger", "triggers", "triggered",
    "become", "becomes", "became", "give", "gives", "given", "inflict",
    "inflicts", "inflicted", "remove", "removes", "removed",
}

# Makine çevirisinin daha önce yanlış anlam verdiği, insan gözüyle doğrulanmış
# kısa arayüz karşılıkları. Denetim, bunların sonraki bir çeviri/güncellemede
# sessizce bozulmasına izin vermez.
CANONICAL_UI_TRANSLATIONS = {
    "achievement.quest.type.1": "Destan",
    "quest.categoryTitle.epic": "Destan",
    "resource.plants": "Bitkiler",
    "desc.emotesInventory": "İfadeler ve Yüz İfadeleri",
    "achievement.reward.aptitude": "Beceri Puanları",
    "ally": "Müttefik",
    "AP": "Aksiyon Puanları",
    "BAGS": "Çantalar",
    "bestiary.label": "Canavar Kitabı",
    "booster.pack.ui.title": "Güçlendirici",
    "BLAZED_SMILEYS": "Bezgin",
    "blindBox.desc.rollSkip": "Aç / Geç",
    "boat.noDestinationAvailable": "Kullanılabilir varış noktası yok",
    "bonusPenalties": "Bonuslar / Cezalar",
    "bonusPointDistributionTable": "Tablolar yükleniyor",
    "booster.pack.inactive": "ETKİN DEĞİL",
    "citizenRank.name.HOODLUM": "Kanun Kaçağı",
    "citizenRank.name.INHABITANT": "Sakin",
    "notification.outlawTitle": "Kanun Kaçağı",
    "tuto.PvpNation.title": "Kanun Kaçağı",
    "options.playability": "Oynanış",
    "min": "En az",
    "max": "En çok",
    "rerollXp.info.notRight": (
        "İkincil karakterler için XP bonusu. Bu bonus, bir Güçlendirici ile "
        "x[#1.1]'ye yükseltilebilir."
    ),
    # Oyun bu arayüz etiketlerini content.15 eşya-adı havuzundan çağırıyor;
    # gerçek eşya adı değiller ve karakter/envanter ekranında çevrilmeliler.
    "content.15.2175": "Cepler",
    "content.15.24267": "Deneyim",
    "content.15.27097": "Yakın Dövüş Ustalığı",
    "content.15.27098": "Menzil Ustalığı",
    "content.15.27099": "Berserk Ustalığı",
    "content.15.27110": "İyileştirme Ustalığı",
    "content.15.29612": "Ara",
    "content.62.2170": "Karanlık Odalar",
    "content.64.11374": '"Astrub - Prologue" ana görevini tamamla (Karanlık Odalar)',
}

# Astrub'un açılış sahnesi oyuncunun gördüğü ilk uzun diyalogdur. Sözcük
# sırasını bozan eski makine çevirilerinin manuel belleğe yeniden sızması,
# yalnız biçim ve İngilizce kalıntısı taramasıyla anlaşılamıyordu. Bu 23 satır
# sahne bütünlüğüyle insan denetiminden geçirilmiştir ve birebir korunur.
CANONICAL_DIALOG_TRANSLATIONS = {
    "quest.astrub.intro.00": "Demek burası Astrub...",
    "quest.astrub.intro.00.00": "Ne? Kapıyı biri mi çalıyor?",
    "quest.astrub.intro.00.01": "Ah... Sırtım...",
    "quest.astrub.intro.00.02": "Ne...? Sen de nereden çıktın{[1*]?:}{[1*]?:}{[1*]?:}, ufaklık?",
    "quest.astrub.intro.00.03": "Sanırım az önce bedenlendim.",
    "quest.astrub.intro.00.04": "Bir yerini incitmedin, değil mi? Biraz merhemim olacaktı...",
    "quest.astrub.intro.00.05": "Şey... Hayır, sanırım iyiyim.",
    "quest.astrub.intro.00.06": "Yüksekten düşmeye alışığım!",
    "quest.astrub.intro.00.07": "Vay canına... Bugünün gençleri de pek dayanıklı.",
    "quest.astrub.intro.00.08": "Kusura bakma{[1*]?:}, ortalığı biraz dağıttım...",
    "quest.astrub.intro.00.09": "Biraz, evet... Hahaha!",
    "quest.astrub.intro.00.10": "Önemli olan, bir yerini incitmemiş olman!",
    "quest.astrub.intro.00.11": "Kendimi tanıtayım: Ben Mammy Pal.",
    "quest.astrub.intro.00.12": "Tanıştığımıza memnun oldum{[1*]?:}! Benim adım [#name].",
    "quest.astrub.intro.00.13": "Oturma odasına geçelim. Orada daha rahat konuşabiliriz.",
    "quest.astrub.intro.00.14": "Ah... Astrub'da sıradan bir gün daha.",
    "quest.astrub.intro.01": '"Goultard" adında biriyle görüşmem gerekiyormuş. Bu, efsanevi kahraman Goultard olmalı!',
    "quest.astrub.intro.02": "Pekâlâ, güneye doğru yola çıkma zamanı!",
    "quest.astrub.intro.03": "Güneye doğru yola çıkıyorsun. Çok geçmeden şehrin koşuşturmacasını geride bırakıyorsun.",
    "quest.astrub.intro.04": "Astrub çevresindeki huzurlu çayırlarda yürümek oldukça keyifli.\\n\\nHer şeye rağmen macerana başlamaya can atıyorsun.",
    "quest.astrub.intro.05": "Önceki bedenlenişin ve Ogrest karşısındaki yenilgin artık yalnızca uzak bir anı...",
    "quest.astrub.intro.06": "Balıkçı Köyü'ne varıyorsun. Daha adımını atar atmaz dövüş sesleri duyuyorsun. Görünüşe göre Goultard'ı buldun.",
    "quest.astrub.intro.07": "Önce Mammy Pal ile konuşmalısın.",
}
CANONICAL_DIALOG_TRANSLATIONS.update({
    "quest.astrub.chacha.01": "Off, burası fena hâlde Bow Meow kokuyor!",
    "quest.astrub.chacha.02": "Geri dur, evlat. Bunu ben hallederim...",
    "quest.astrub.chacha.03": "Ne? Olmaz öyle şey. Ben de dövüşeceğim!",
    "quest.astrub.chacha.04": "**Bu ufaklık dövüşmekte gerçekten çok iyi...",
    "quest.astrub.chacha.05": "Muhteşem saldırılarımı gördün mü?",
    "quest.astrub.chacha.06": "Hadi gidelim! Usta Goultard'ın bana daha ilginç bir görev vermesini sabırsızlıkla bekliyorum!",
    "quest.astrub.chacha.07": "Şimdiye kadar gayet iyi gidiyoruz!",
    "quest.astrub.chacha.08": "Devam edelim! Boss artık çok uzakta olamaz!",
    "quest.astrub.chacha.09": "Yardım edin! Lütfen, kurtarın beni! Bow Meow'lar beni yemek istiyor!",
    "quest.astrub.chacha.10": "Vay canına! İnanılır gibi değil! Şuna benziyor...",
    "quest.astrub.chacha.11": "Neye benziyor?",
    "quest.astrub.chacha.12": "Bu...",
    "quest.astrub.chacha.13": "Ne olduğunu bilmiyorum.",
    "quest.astrub.chacha.14": "Harika...",
    "quest.astrub.chacha.15": "Ben yalnızca zararsız bir Gemlin'im! Beni kurtar, sana yardım edeyim!",
    "quest.astrub.chacha.16": "İşte bu! Sanırım sonuncusu da buydu.",
    "quest.astrub.chacha.17": "Bana yardım ettiğiniz için çok teşekkür ederim!",
    "quest.astrub.chacha.18": "Buradaki Bow Meow'lar son zamanlarda iyice hırçınlaştı.",
    "quest.astrub.chacha.19": "Belki de deniz havasıyla ilgili bir şeydir...",
    "quest.astrub.chacha.20": "Ben [#name], bu da Percedal.",
    "quest.astrub.chacha.21": "Tanıştığımıza memnun oldum, [#name]! Yolculuğuna ben de katılayım.",
    "quest.astrub.chacha.22": "Çok faydalı olabilirim, göreceksin!",
    "quest.astrub.chacha.23": "Nihayet temiz hava... Bow Meow kokusuna daha fazla dayanamıyordum.",
    "quest.astrub.chacha.24": "Dikkat!!!",
    "quest.astrub.chacha.25": "Sanırım Bow Meow'ları huzursuz eden şeyi bulduk.",
    "quest.astrub.chacha.26": "Ah ha ha, sonunda adına yaraşır bir boss!",
    "quest.astrub.chacha.27": "Usta Goultard, hayır!!!",
    "quest.astrub.chacha.28": "Her zamanki gibi gözü pek Goultard işe el atınca dev Nekark'ın işi çabucak bitiyor.",
    "quest.astrub.chacha.29": "Percedal bu destansı savaşa katılamadığı için gerçekten hayal kırıklığına uğramış görünüyor...\\n\\nOlanları anlatmak için Goultard'ın yanına dönüyorsun.",
    "quest.astrub.chacha.30": "Üzülmeye son... Goultard yetişti, kurtuluş yakın!",
    "quest.astrub.ullu.1": "Bakalım...",
    "quest.astrub.ullu.2": "SEN!!! Sensin!",
    "quest.astrub.ullu.3": "Kehanette sözü edilen kahraman{[1*]?:}{[1*]?:} sensin... Bundan hiç şüphem yok!",
    "quest.astrub.ullu.4": "Dünyada kalan on iki eseri topla!",
    "quest.astrub.ullu.4.2": "Hemen Zinit Dağı'nda yanıma gel!!",
    "quest.astrub.ullu.5": "Kaderinde Zinit Dağı'na tırmanmak ve...",
    "quest.astrub.ullu.6": "OGREST'İ YENMEK VAR!!!",
    "quest.astrub.ullu.7": "Ben, Tanrıların elçisi Ullu, seni gözümün önünden ayırmayacağım!",
    "quest.astrub.ullu.8": "Kehanetin kahramanı{[1*]?:}... Seni Zinit Dağı'nda bekliyor olacağım!",
})

MECHANIC_POINT_SOURCE_RE = re.compile(
    r"(?i)(?:action|skill|specialty|experience|movement|wakfu|mastery|agility|ability|"
    r"aptitude|characteristic|conquest|score|citizenship|health|life|intelligence|"
    r"chance|strength|wisdom|prospecting|leadership|heal|range|guild|resource)\s+points?|"
    r"\bpoints?\s+(?:to distribute|available|remaining|earned|gained|lost|spent|bonus|penalty)"
)


def joined_english_word(source, target, protected_names=None):
    """Find an English source word glued to another word in the translation.

    Looking at the source tokens avoids false positives in proper names such as
    Chester/Chestnut and ordinary Turkish words that merely contain an English
    substring.
    """
    ignored = {"the", "and", "for", "with", "from", "into", "that", "this", "your", "their", "have", "will"}
    source_visible = re.sub(r"https?://\S+", " ", strip_protected_names(visible_text(source), protected_names))
    target_visible = re.sub(r"https?://\S+", " ", strip_protected_names(visible_text(target), protected_names))
    source_words = {
        word.casefold() for word in re.findall(r"[A-Za-z]+", source_visible)
        if len(word) >= 4 and word.casefold() not in ignored
        and word.casefold() not in ALLOWED_IDENTICAL_WORDS
    }
    target_words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", target_visible)
    turkish_suffixes = {
        "ı", "i", "u", "ü", "a", "e", "yı", "yi", "yu", "yü", "ya", "ye",
        "ın", "in", "un", "ün", "nın", "nin", "nun", "nün", "ım", "im", "um", "üm",
        "ımız", "imiz", "umuz", "ümüz", "ınız", "iniz", "unuz", "ünüz",
        "da", "de", "ta", "te", "dan", "den", "tan", "ten", "daki", "deki",
        "lar", "ler", "ları", "leri", "ların", "lerin", "lara", "lere", "larda", "lerde",
        "lardan", "lerden", "la", "le", "lı", "li", "lu", "lü",
        "ına", "ine", "una", "üne",
        "dır", "dir", "dur", "dür", "tır", "tir", "tur", "tür", "sı", "si", "su", "sü",
        "ını", "ini", "unu", "ünü", "ında", "inde", "unda", "ünde",
        "ının", "inin", "unun", "ünün", "ından", "inden", "undan", "ünden",
    }
    for target_word in target_words:
        folded = target_word.casefold()
        for word in source_words:
            if len(folded) <= len(word):
                continue
            if folded.startswith(word):
                remainder = target_word[len(word):]
                if remainder.casefold() in turkish_suffixes:
                    continue
                if word in JOINABLE_ENGLISH_WORDS or (remainder and remainder[0].isupper()):
                    return target_word
            if folded.endswith(word):
                start = len(target_word) - len(word)
                if word in JOINABLE_ENGLISH_WORDS or (start > 0 and target_word[start].isupper()):
                    return target_word
    return ""


def copied_source_word(source, target, protected_names=None):
    """Return a visible English source word copied into the Turkish output.

    The static English list catches common UI words, while this source-aware
    check finds corpus-specific leftovers such as "nagged" and "elemental".
    Proper WAKFU names and accepted technical/loan words are removed first.
    """
    # Bazı günlükler bulmaca gereği karakter karakter ters yazılmıştır. Bu
    # metinlerde Bwork/Harebourg gibi özel adlar da ters görünür ve olağan
    # İngilizce sözcük taraması bunları yanlışlıkla kalıntı sayar.
    reversed_markers = re.findall(r"(?i)\b(?:eht|dna|rof|lliw|evah|si)\b", source)
    if len(reversed_markers) >= 3:
        return ""
    # Gender/plural branches are localization engine grammar. Their branch
    # labels can contain English fragments (for example istress/aster), but
    # those fragments are not visible untranslated prose and must not be
    # compared as copied source words.
    source_for_words = re.sub(r"\{\[[^\]]+\]\?[^{}]*\}", " ", source)
    target_for_words = re.sub(r"\{\[[^\]]+\]\?[^{}]*\}", " ", target)
    source_visible = re.sub(r"https?://\S+", " ", visible_text(source_for_words))
    target_visible = re.sub(
        r"https?://\S+", " ",
        strip_protected_names(visible_text(target_for_words), protected_names),
    )
    target_words = {
        word.casefold() for word in re.findall(r"[A-Za-z]+", target_visible)
    }
    for index, match in enumerate(re.finditer(r"[A-Za-z]+", source_visible)):
        word = match.group(0)
        folded = word.casefold()
        if len(folded) < 4 or folded in ALLOWED_IDENTICAL_WORDS:
            continue
        if folded not in target_words:
            continue
        # Drago-Express, WAKFU'nun ulaşım sisteminin özel adıdır; yalnız bu
        # birleşik ad içindeki “express” İngilizce kalıntısı sayılmaz.
        if folded == "express" and re.search(r"(?i)\bdrago-express\b", target_visible):
            continue
        # “Tour Yst”, turist sözcüğüne gönderme yapan kurgusal yaratık adıdır.
        if folded == "tour" and re.search(r"(?i)\btour\s+yst(?:ler)?\b", target_visible):
            continue
        # Capitalized corpus names may be absent from an older protected-name
        # snapshot. Generic game terms remain translatable even when capitalized.
        if word[:1].isupper() and folded not in GENERIC_TRANSLATABLE_WORDS:
            continue
        return word
    return ""
MISSPELLING_RE = re.compile(
    r"(?i)\b(yanlız|herşey|birşey|hiçbirşey|şuan|orjinal|değilmi|yalnış|ne oldu\d+|"
    r"yeterince iyileştim|kullanıcı adınız|satın alma fırsatı|sıfırsa sahip|zerosa sahip|"
    r"görüşüm açıldı|pencerem ekleyemezsiniz|pencerem kayıt|kilitedeki|onaylıyormusunuz|dağıttiniz|"
    r"güvenlikler|emin misiniz ki|pazar yeri['’]de|savaş alanı katıl|satırsınız|yapı et|"
    r"kaster|kastör|monstrolar|weapons usta)\b"
)
# Yalnız gerçekten ad taşıyan içerik aileleri kilitlenir. content.6/8
# (etki-buff adları), 33 (mekanik açıklamalar), 34 (unvanlar), 35
# (etkileşim/mekân metinleri) ve 62 (görev-etkinlik başlıkları) Türkçeye
# çevrilebilir; bunları bütünüyle korumak binlerce gerçek eksiği gizliyordu.
PROTECTED_CONTENT_RE = re.compile(r"^content\.(3|7|12|15|20|38|48|54|77|78|82|89|130|159)\.")
LINKED_ITEM_PREFIXES = (
    "content.6.", "content.8.",
)
VISIBLE_WORLD_LABEL_PREFIXES = (
    "content.35.", "content.54.", "content.59.", "content.66.", "content.77.", "content.78.",
    "content.79.", "content.81.", "content.82.", "content.83.", "content.88.",
    "content.89.", "content.93.", "content.96.", "content.106.", "content.122.",
    "content.124.", "content.126.", "content.137.", "content.140.", "content.151.",
    "content.155.", "content.158.", "content.161.",
)
VISIBLE_WORLD_DESCRIPTOR_RE = re.compile(
    r"(?i)\b(?:house|houses|dungeon|cave|cavern|lair|island|prison|hall|rift|"
    r"mine|mines|sewers|village|outpost|warehouse|bridge|garden|camp|zone|"
    r"battlefield|stadium|field|swamp|swamps|forest|harbou?r|docks?|tavern|"
    r"inn|room|kitchen|laboratory|beach|shore|canyon|temple|sanctuary|refuge|"
    r"passageway|gallery|galleries|ruins|crypt|tomb|estate|factory|tunnel|"
    r"hollow|tower|palace|castle|road|prairie|plains|mountains|park|workshop|"
    r"office|school|bunk|upstairs|downstairs|quarters|headquarters|hq|cellar|"
    r"basement|ship|boat|deck|store|storeroom|arena|capital|kingdom|territory|"
    r"gate|gateway|entrance|exit|access|interior|exterior|district|square|"
    r"market|port|platform|roof|path|passage|abyss|den|grove|graveyard|"
    r"cemetery|walls?|door|ladder|bed|library|bank|clinic|farm|mill|sawmill|"
    r"forge|well|fountain|station|academy|chamber|hideout|hideaway|wing|hold|"
    r"pier|reservoirs?|archive|archives|avenue|street|boulevard|alley|crossway|"
    r"floor|center|north|south|east|west|depths|underground|suburbs|tunnels?|"
    r"drago-express|canoon|altar|oven|lathe|setter|armory|stove|distillery|"
    r"polisher|millstone)\b"
)
VISIBLE_WORLD_GENERIC_SINGLE = {
    "alley", "altar", "anvil", "attic", "bank", "barrel", "basement",
    "bed", "boat", "book", "bridge", "camp", "cauldron", "cave", "center",
    "chamber", "clinic", "cube", "desk", "disco", "dock", "door", "downstairs",
    "east", "entrance", "exit", "factory", "farm", "feeder", "field", "fountain",
    "furrower", "gate", "generator", "grave", "hall", "inn", "ladder", "lever",
    "library", "market", "mine", "minecart", "north", "office", "park", "pillar",
    "platform", "port", "prison", "puffball", "refuge", "restaurant", "road", "rock",
    "roof", "room", "rudder", "ruins", "safe", "school", "sewers", "shore", "south",
    "stairs", "stasilizer", "station", "stele", "store", "switch", "temple", "tomb",
    "tombstone", "tower", "trap", "tunnel", "underground", "upstairs", "village",
    "wall", "warehouse", "west", "wheeturn", "workshop",
}


def is_visible_world_text(source):
    shown = re.sub(r"<[^>]+>", " ", source.replace("\\n", " "))
    words = re.findall(r"[A-Za-zÀ-ž][A-Za-zÀ-ž'’-]*", shown)
    if source.strip().casefold() in VISIBLE_WORLD_GENERIC_SINGLE:
        return True
    if VISIBLE_WORLD_DESCRIPTOR_RE.search(shown):
        return True
    lower_starts = sum(word[:1].islower() for word in words)
    if len(words) >= 4 and lower_starts >= 2 and (
        "\\n" in source or "<" in source or re.search(r"[.!?;:]", source)
    ):
        return True
    return len(words) >= 7 and lower_starts >= 3
REVIEWED_TRANSLATABLE_NAME_KEYS = {
    # content.15 içinde saklanmalarına rağmen bunlar gerçek eşya adı değil,
    # envanter/karakter ekranında kullanılan arayüz etiketleridir.
    "content.15.2175",   # Pockets
    "content.15.11955",  # Giga Piwipouch (envanter depo başlığı)
    "content.15.15865",  # Ample Miner Box (envanter depo başlığı)
    "content.15.19799",  # Component Basket (envanter depo başlığı)
    "content.15.24267",  # Experience (ödül arayüzü etiketi)
    "content.15.27097",  # Melee Mastery
    "content.15.27098",  # Distance Mastery
    "content.15.27099",  # Berserk Mastery
    "content.15.27110",  # Healing Mastery
    "content.15.29612",  # Search
    "content.15.31167",  # Celestial Bag (envanter depo başlığı)
    # Kitap başlıkları ve nadirlikte görünen genel etiketler oyuncuya Türkçe
    # gösterilir; özel kişi, yaratık ve ekipman adları bu listenin dışındadır.
    "content.15.18628",  # Dragoturkey Stories
    "content.15.18629",  # How to Cook your Dragoturkey
    "content.15.18630",  # Harnessing and Saddling
    "content.15.19056",  # Souvenir
    "content.15.20020",  # Spherolithic Encyclopedia
    "content.15.20021",  # Abacus Compendium
    "content.15.22385",  # Souvenir
    "content.15.24027",  # Dathura Souvenir
    "content.15.24081",  # Dathura Souvenir
    "content.15.24845",  # Iopunchup Battlefield Rules
    "content.15.24846",  # Enipsia Battlefield Rules
    "content.15.25103",  # Battlefield Rules: Free-for-All
    "content.15.32542",  # Ancestral Souvenir
    "content.15.32543",  # Ancestral Souvenir
    "content.38.5",      # Summons (creature family label)
    "content.38.518",    # Guild of Hunters
    "content.61.517",    # Guild of Hunters
    "content.78.336",    # Guild of Hunters' Camp
    "content.78.354",    # Guild of Hunters' Camp
    "content.78.368",    # Guild of Hunters' Camp
    "content.78.379",    # Guild of Hunters' Camp
    "content.54.1620",   # Fishermen's Hamlet (generic location label)
    "content.7.5062",    # Prevent then Heal
    "content.7.4037",    # Wakfu Harvester
    "content.7.4038",    # Wakfu Harvester
    # Sınıf tanıtım kartındaki sekme başlığıdır; savaş içi durum adı değildir.
    "content.8.1263", "content.8.2718", "content.8.4048",
    "content.8.4260", "content.8.5817", "content.8.5865",
    "content.8.7386",
    # Genel arayüzde gösterilen istatistik/dünya bonusu etiketleridir;
    # bir yetenek veya savaş mekaniği adı değildir.
    "content.8.748",   # Prospecting
    "content.8.5355",  # Territory Control Bonus
    "content.8.1915",  # Area bonus (general region bonus title)
    "content.8.1916",  # Area bonus (general region bonus title)
    "content.8.3430",  # Sharpening
    "content.8.7757",  # Precision Shot
    "content.8.7792",  # Precision
}

# Aynı kitap/nadirlik metni yeni bir content.15 anahtarıyla tekrar gelirse,
# anahtarın önceden listelenmesini beklemeden güvenli biçimde çevrilebilsin.
TRANSLATABLE_GENERIC_NAME_VALUES = {
    "Dragoturkey Stories": "Dragoturkey Hikâyeleri",
    "How to Cook your Dragoturkey": "Dragoturkey Nasıl Pişirilir?",
    "Harnessing and Saddling": "Koşum Takımı ve Eyerleme",
    "Souvenir": "Hatıra",
    "Spherolithic Encyclopedia": "Sferolitik Ansiklopedi",
    "Abacus Compendium": "Abakus Derlemesi",
    "Dathura Souvenir": "Dathura Hatırası",
    "Iopunchup Battlefield Rules": "Iopunchup Savaş Alanı Kuralları",
    "Enipsia Battlefield Rules": "Enipsia Savaş Alanı Kuralları",
    "Battlefield Rules: Free-for-All": "Savaş Alanı Kuralları: Herkes Tek Başına",
    "Ancestral Souvenir": "Atasal Hatıra",
}
REVIEWED_PROTECTED_KEYS = {
    # Etki/durum ailelerinde bulunmalarına rağmen bunlar oyuncuya gösterilen
    # gerçek WAKFU adlarıdır; açıklama veya arayüz cümlesi değildir.
    "content.6.789",   # Barrel of Weapons
    "content.6.1851",  # Sadida Seed (Nettled level 1)
    "content.6.1852",  # Sadida Seed (Nettled level 2)
    "content.6.1853",  # Sadida Seed (Nettled level 3)
    "content.6.1854",  # Sadida Seed (Nettled level 4)
    "content.6.2135",  # Teleportation Trap II
    "content.6.1049",  # Will-o-the-Wisp (yetenek içi özgün ad başvurusu)
    "content.8.923",   # Louie Gee Light
    "content.8.1555",  # Concentration Listening
    "content.8.1964",  # Explosive Concentration
    "content.8.1965",  # Striking Concentration
    "content.8.3425",  # Concentration Management
    "content.8.3430",  # Sharpening
    "content.33.178524",  # Boomerang Hammer! (eşya adı çağrısı)
    "content.33.393883",  # Nox
    "content.33.394159",  # Count Harebourg
    "content.8.3431",  # Sharpened Arrowhead
    "content.8.3442",  # Concentration
    "content.8.4092",  # Mastery of Weapons
    "content.8.5449",  # Elemental Concentration
    "content.8.7526",  # Were-Ouginak
    "content.8.7757",  # Precision Shot
    "content.8.7792",  # Precision
    "content.8.8306",  # Stasis Concentration
    "content.8.8743",  # Night-light
    "content.8.9048",  # Miner Azure Dragon
}

# Kaynağın kendisi ters yazı, bozuk ipucu veya ses taklidi olduğundan sıradan
# İngilizce/noktalama kurallarıyla ölçülemeyen; biçimi ayrıca doğrulanmış metinler.
REVIEWED_NONLEXICAL_KEYS = {
    "content.67.687",
    "mercenaries.help",
    "quest.mercenaire.zinit.sacri.q2.02",
    "quest.saharach.comportementCacterre4",
}

# Eşya adıyla birebir aynı olsa da ekranda gerçek görev/başarım başlığı olarak
# kullanılan doğrulanmış çakışmalar. Bunlar yanlışlıkla İngilizceye sabitlenirse
# denetim bunu insan onaylı kayıt sayıp geçmemelidir.
TRANSLATABLE_QUEST_ITEM_COLLISION_KEYS = {
    "content.62.2913",  # Message in a Bottle görev başlığı
}

EXPLICIT_PROTECTED_WORLD_LABELS = {
    # Canoon, WAKFU'nun top biçimli ulaşım aracının özel adıdır; sıradan
    # "cannon" sözcüğü gibi çevrilmez. Moon-Canoon da aynı ad ailesindedir.
    "Canoon",
    "Moon-Canoon",
}

# Açıklama ve görev cümlelerinde İngilizce kalması bilinçli olan gerçek WAKFU
# büyü, durum ve kişi adları. Bunlar genel İngilizce kalıntı taramasından önce
# çıkarılır; çevresindeki cümle yine tam olarak denetlenir.
EXPLICIT_PROTECTED_NAMES = {
    "Will-o'-the-Wisp",
    "Will-o'-the-Wisps",
    *EXPLICIT_PROTECTED_WORLD_LABELS,
    # Oyuncunun tercih ettiği ad politikası: bağlantılı yetenek, mod, sayaç
    # ve durum adları açıklama Türkçe olsa da resmî İngilizce adıyla kalır.
    "Abundance",
    "Berserker",
    "Calm",
    "Cataclysm",
    "Dagger Return",
    "Escapist",
    "Exaltation",
    "Exalted",
    "Feline Leap",
    "Flame Return",
    "Flame Returns",
    "Flaming",
    "High Pressure",
    "Incurable",
    "Invisibility",
    "Invisible",
    "Lucky Day",
    "Nettled",
    "Portal",
    "Principio Valere",
    "Propagator",
    "Punishment",
    "Roll Again",
    "Runaway",
    "Rusty Blades",
    "Sacrificial Doll",
    "Sadida Seed",
    "Sadist Mark",
    "Shiny Orb",
    "Sneaky",
    "Sneaky Blade",
    "Standard",
    "Summoning of the Roots",
    "The Sacrificial Doll",
    "Visio Imperum",
    "Wrath",
    "Incan'rune",
    "Aqua'rune",
    "Tellu'rune",
    "Aer'rune",
    "Passage of Time",
    "Were-Summons",
    "Back to Back",
    "Emote-If",
    "May",
    # Kaynak içinde bilinçli korunan yetenek/eşya/NPC adları ve karakterin
    # yabancı dildeki selamı. Bunlar Türkçe cümlede İngilizce kalıntısı değildir.
    "Sic 'Em More",
    "Vild Vest",
    "Vild Vest'i",
    "Buenos dias",
    "Grumble Mouth",
    "Still Book",
    "Fluffy Block",
    "Brâkmar",
    "The IUB",
    "Biduule",
}
MANUAL_PROTECTED_TRANSLATION_KEYS = {
    "content.33.345405",
    "content.33.401238",
}
MANUAL_PROTECTED_TRANSLATION_KEYS.update(CLEAN_SOURCE_SEMANTIC_REPAIRS)
MANUAL_PROTECTED_TRANSLATION_KEYS.update(SEMANTIC_EXACT_V123)

NOX_REVIEWED_TRANSLATION_KEYS = {
    "content.33.407373",
    "content.33.407374",
    "content.33.407396",
    "content.33.407439",
    "content.33.407476",
    "content.33.407488",
    "content.33.407540",
    "content.33.407580",
    "content.33.407584",
    "content.33.407585",
    "content.33.407588",
    "content.33.407596",
    "content.33.407597",
    "content.33.407600",
    "content.33.407601",
    "content.33.407614",
    "content.33.407652",
    "content.33.407657",
    "content.33.407670",
    "content.33.407739",
    "content.33.407740",
    "content.33.407749",
    "content.33.407751",
    "content.33.407764",
    "content.33.407765",
    "content.33.407766",
    "content.33.407767",
    "content.33.407771",
    "content.33.407780",
    "content.33.407803",
    "content.33.407815",
    "content.33.407826",
    "content.33.407832",
    "content.33.407837",
    "content.33.407839",
    "content.33.407843",
    "content.33.407846",
    "content.33.407859",
    "content.33.407860",
    "content.33.407861",
    "content.33.407872",
    "content.33.407874",
    "content.33.407878",
    "content.33.407882",
    "content.33.407886",
}
MANUAL_PROTECTED_TRANSLATION_KEYS.update(NOX_REVIEWED_TRANSLATION_KEYS)

HAVEN_FEATURE_SOURCE_RE = re.compile(
    r"(?i)\b(?:Haven\s+(?:Bags?|Worlds?|Places?|Gems?|Moods?)|Tree\s+Havens)\b"
)


def is_reviewed_haven_translation(source, target):
    return bool(
        HAVEN_FEATURE_SOURCE_RE.search(source)
        and re.search(r"(?iu)\bsığınak", target)
    )


def is_translatable_inventory_name(key, source):
    """Only reviewed generic inventory/book labels may be translated."""
    return key.startswith(("content.8.", "content.15.")) and (
        key in REVIEWED_TRANSLATABLE_NAME_KEYS
        or source.strip() in TRANSLATABLE_GENERIC_NAME_VALUES
    )


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def read_properties(jar_path):
    with zipfile.ZipFile(jar_path, "r") as archive:
        name = "texts_en.properties"
        if name not in archive.namelist():
            name = "texts_en_cleaned.properties"
        with archive.open(name, "r") as raw:
            for binary_line in raw:
                line = binary_line.decode("utf-8-sig").rstrip("\r\n")
                if not line or line.startswith(("#", "!")) or "=" not in line:
                    continue
                key, source = line.split("=", 1)
                yield key, source


def is_protected_key(key):
    # Oyuncu tercihi: büyü/yetenek, savaş içi durum ve eşya başlıkları özgün
    # İngilizce adıyla gösterilir. Arayüz sekmeleri ve açıklamalar çevrilebilir.
    if key in REVIEWED_PROTECTED_KEYS:
        return True
    if (
        key in REVIEWED_TRANSLATABLE_NAME_KEYS
        or key in MANUAL_PROTECTED_TRANSLATION_KEYS
    ):
        return False
    if key.startswith(("content.3.", "content.8.", "content.15.")):
        return True
    return bool(
        PROTECTED_CONTENT_RE.match(key)
        or re.match(r"^breed\.\d+$", key)
        or ".boussole." in key or key.startswith(("boussole.", "worldName."))
        or re.match(r"^desc\.mru\.activate\.[^.]+\.[^.]+$", key)
        or re.match(r"(?i)^(item|monster|mob|npc|spell|skill|pet|mount)\..*\.name$", key)
    )


def category(key):
    numeric = (
        ("content.3.", "YETENEK_ADI"), ("content.6.", "YETENEK_ETKI_ADI"),
        ("content.7.", "YARATIK_ADI"), ("content.8.", "BUFF_DURUM_ADI"),
        ("content.12.", "KAYNAK_ADI"), ("content.15.", "ESYA_KAYNAK_ADI"),
        ("content.20.", "ESYA_SETI_ADI"), ("content.38.", "YARATIK_AILESI_ADI"),
        ("content.33.", "TEKNIK_ETKI_KALIBI"), ("content.34.", "WAKFU_UNVAN_ADI"),
        ("content.35.", "NPC_ETKILESIM_MEKAN_ADI"), ("content.54.", "MEKAN_ADI"),
        ("content.61.", "BASARIM_KATEGORISI"), ("content.62.", "BASARIM_ADI"),
        ("content.77.", "MEKAN_ADI"),
        ("content.78.", "NPC_YARATIK_ADI"), ("content.89.", "MEKAN_ADI"),
        ("content.82.", "ULASIM_OZEL_ADI"),
        ("content.48.", "NPC_ADI"), ("content.159.", "NPC_ADI"),
        ("content.130.", "KARAKTER_ADI"),
        ("content.157.", "OZEL_MEKAN_ADI"), ("content.16.", "ESYA_ACIKLAMA"),
    )
    for prefix, result in numeric:
        if key.startswith(prefix):
            return result
    if re.match(r"^breed\.\d+$", key): return "SINIF_ADI"
    if key.startswith("breed.role.name."): return "SINIF_ROLU"
    if key.startswith("breed.role.desc."): return "SINIF_ROL_ACIKLAMASI"
    if key.startswith("breed."): return "KARAKTER_OLUSTURMA"
    if re.match(r"^content\.(4|9|10|13|30|33|146)\.", key): return "MEKANIK_BUFF_ACIKLAMA"
    if re.match(r"^content\.(55|87|101|102)\.", key): return "PAZAR_TICARET"
    if re.match(r"^content\.(64|76)\.", key): return "GOREV_HEDEF"
    if re.match(r"^content\.(47|49|63|75)\.", key): return "DIYALOG_HIKAYE"
    if re.match(r"^content\.(65|67|156)\.", key): return "REHBER_EGITIM"
    if re.search(r"(?i)(market|auction|shop|trade|exchange|seller|purchase|sale)", key): return "PAZAR_TICARET"
    if re.search(r"(?i)(quest|objective|mission|achievement)", key): return "GOREV_HEDEF"
    if re.search(r"(?i)(dialog|speech|monologue|conversation|talk|chat|wabbit)", key): return "DIYALOG_HIKAYE"
    if re.search(r"(?i)(tutorial|guide|help|tip)", key): return "REHBER_EGITIM"
    if re.search(r"(?i)(buff|effect|state|status|damage|mastery|resistance|armor|heal)", key): return "MEKANIK_BUFF_ACIKLAMA"
    if re.search(r"(?i)(item.*desc|description|tooltip|details)", key): return "ESYA_ACIKLAMA"
    if re.search(r"(?i)(ui|window|button|menu|option|inventory|character|build|interface|label|popup|panel)", key): return "ARAYUZ"
    return "GENEL_OYUN_METNI"


def format_spans(text):
    spans = []

    def walk(start, stop):
        index = start
        while index < stop:
            if text.startswith("{[", index):
                condition_end = text.find("]?", index + 2, stop)
                if condition_end >= 0:
                    body_start = condition_end + 2; depth = 0; separator = None; cursor = body_start; close = None
                    while cursor < stop:
                        if text.startswith("{[", cursor): depth += 1; cursor += 2; continue
                        if text[cursor] == "}":
                            if depth: depth -= 1; cursor += 1; continue
                            close = cursor; break
                        if text[cursor] == ":" and depth == 0 and (cursor == 0 or text[cursor - 1] != "\\") and separator is None:
                            separator = cursor
                        cursor += 1
                    if close is not None and separator is not None:
                        spans.append((index, body_start, text[index:body_start])); walk(body_start, separator)
                        spans.append((separator, separator + 1, ":")); walk(separator + 1, close)
                        spans.append((close, close + 1, "}")); index = close + 1; continue
            match = FORMAT_TOKEN_RE.match(text, index)
            if match:
                spans.append((index, match.end(), match.group(0))); index = match.end(); continue
            index += 1

    walk(0, len(text))
    spans.sort(key=lambda item: (item[0], item[1]))
    return spans


def format_tokens(text):
    return [value for _, _, value in format_spans(text)]


def visible_text(text):
    chars = list(text)
    for start, end, _ in format_spans(text):
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def strip_protected_names(text, protected_names):
    """Remove known Wakfu proper names before the English-residue check."""
    if not protected_names:
        return text
    words = list(re.finditer(r"[^\W_]+(?:['’\-][^\W_]+)*", text, re.UNICODE))
    spans = []
    index = 0
    while index < len(words):
        found = None
        for end_index in range(min(len(words) - 1, index + 7), index - 1, -1):
            start, end = words[index].start(), words[end_index].end()
            candidate = re.sub(r"\s+", " ", text[start:end].strip().rstrip(".,;:!?"))
            # Özgün adlara Türkçe ek kesmeyle bağlanabilir:
            # Teleportation Trap'e, Were-Ouginak'a gibi.
            unsuffixed = re.sub(r"['’][A-Za-zÇĞİÖŞÜçğıöşü]{1,6}$", "", candidate)
            if (
                candidate in protected_names
                or candidate.casefold() in protected_names
                or unsuffixed in protected_names
                or unsuffixed.casefold() in protected_names
            ):
                found = (start, end)
                index = end_index + 1
                break
        if found:
            spans.append(found)
        else:
            index += 1
    chars = list(text)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def strip_probable_proper_names(text):
    """Ignore multi-word Wakfu names whose English connector words are intentional."""
    pattern = re.compile(
        r"\b[A-ZÀ-Ž][\wÀ-ž'’\-]*(?:(?:\s+|[-'’])(?:the|of|and|in|on|at|to|from|"
        r"[A-ZÀ-Ž][\wÀ-ž'’\-]*)){1,7}\b"
    )
    return pattern.sub(" ", text)


def format_ok(source, target):
    # Kaynakta tek bir ``\n`` varken çeviride ``\\n`` bulunması oyunda
    # gerçek satır sonu yerine görünür "\n" yazdırır.
    if "\\\\n" in target and "\\\\n" not in source:
        return False
    source_tokens = format_tokens(source)
    target_tokens = format_tokens(target)
    if source_tokens == target_tokens:
        return True
    # The upstream cleaned properties copy is lower-cased, including
    # placeholder names.  The JAR builder already restores source spelling;
    # audit the shared translation memory by token identity, not casing.
    if [value.casefold() for value in source_tokens] == [value.casefold() for value in target_tokens]:
        return True

    # Deeply nested Wakfu conditionals occasionally contain natural punctuation
    # that confuses the recursive tokenizer.  Compare a strict structural
    # signature as a safe fallback: every condition, placeholder, tag and
    # branch boundary must still be present in the same quantity/order.
    header_re = re.compile(r"\{\[[^\]]+\]\?")

    def conditional_headers(text):
        result = []
        for match in header_re.finditer(text):
            depth = 1
            separator_found = False
            closed = False
            for char in text[match.end():]:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        closed = True
                        break
                elif char == ":" and depth == 1:
                    separator_found = True
            if not closed or not separator_found:
                return None
            result.append(match.group(0))
        return tuple(result)

    def signature(text):
        headers = header_re.findall(text)
        without_headers = header_re.sub("", text)
        ordinary = re.findall(
            r"\\[ntr]|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|%[A-Za-z_][A-Za-z0-9_.-]*%|"
            r"\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]",
            without_headers,
        )
        return headers, ordinary, conditional_headers(text), text.count("{"), text.count("}")

    return signature(source) == signature(target)


def complete(source, target):
    if not source.strip() or not target.strip():
        return False
    clean_source = visible_text(source)
    clean_target = visible_text(target)
    source_words = len(re.findall(r"[^\W\d_]+", clean_source, re.UNICODE))
    target_words = len(re.findall(r"[^\W\d_]+", clean_target, re.UNICODE))
    if source_words >= 8 and target_words < max(1, int(source_words * 0.25 + 0.999)):
        return False
    return not (
        len(clean_source) >= 45
        and len(clean_target) < int(len(clean_source) * 0.35 + 0.999)
    )


def analyze(
    key,
    source,
    target,
    protected_value=False,
    protected_names=None,
    reviewed_key=False,
    trusted_translation=False,
):
    canonical = CANONICAL_UI_TRANSLATIONS.get(key)
    if canonical is None:
        canonical = CANONICAL_DIALOG_TRANSLATIONS.get(key)
    # İnsan onaylı manual repair, sözlükteki eski/otomatik kanonik karşılıktan
    # bilinçli olarak farklı olabilir. Öncelik manual > TM > glossary olduğundan
    # bu kayıtlar kanonik sözlükle ezilmez; biçim ve diğer güvenlik kontrolleri
    # aşağıda yine çalışmaya devam eder.
    if canonical is not None and target != canonical and not trusted_translation:
        return "YANLIS_TERIM", f"Doğrulanmış arayüz karşılığı kullanılmalı: {canonical}", True
    visible_target = re.sub(r"https?://\S+", " ", visible_text(target))
    if key in REVIEWED_NONLEXICAL_KEYS:
        if not format_ok(source, target):
            return "BICIM_HATASI", "İnsan denetimli özel metinde biçim kodları kaynakla eşleşmiyor", True
        return "CEVRILDI", "Ters yazı, bozuk ipucu veya ses taklidi insan tarafından doğrulandı", False
    if re.search(r"(?iu)[^\W\d_]\?'[a-zçğıöşü]", visible_target):
        return "BOZUK_KODLAMA", "Soru işareti Türkçe ekin önüne sızmış; kaynak ad ve ek yeniden kurulmalı", True
    if re.search(r"(?iu)[^\W\d_]\?[^\W\d_]", visible_target):
        return "BOZUK_NOKTALAMA", "Soru işaretinden sonra boşluk eksik veya Türkçe karakter '?' işaretine bozulmuş", True
    if target.strip() == source.strip() and (
        is_protected_key(key)
        or key in REVIEWED_PROTECTED_KEYS
        or protected_value
    ):
        if not format_ok(source, target):
            return "BICIM_HATASI", "Değişken, etiket veya koşul kodları kaynakla eşleşmiyor", True
        return "KORUNAN_AD", "Yetenek, eşya veya savaş durumu adı kullanıcı tercihiyle özgün İngilizce bırakıldı", False
    # Kaynakla karşılaştırılması gereken anlam hataları korunan ad/insan onayı
    # dallarından önce denetlenir. Böylece eski elle, GPU veya model üretimi bir
    # kayıt yalnızca daha önce kaydedildiği için temiz sayılmaz.
    action_check_target = strip_protected_names(target, protected_names)
    if re.search(r"(?i)(?<!Were-)\b(?:Adds?|Summons?|Summoned|Inflicts?|Inflicted|Attracts?|Teleports?|Increases?|Grants?|Applies|Removes?|Steals?|Unbewitches|Requires|Unlocks?)\b|\bGuild of\b", action_check_target):
        return "INGILIZCE_KALINTISI", "Oyuncuya gösterilen metinde çevrilmemiş İngilizce eylem veya genel ad kaldı", True
    if (
        re.search(r"(?i)(?:^|\\n|\n)\s*-?\s*Defeat\s+[^-\s]", source)
        and re.search(r"(?iu)(?:^|\\n|\n)\s*-?\s*Yenilgi\s+", target)
    ):
        return "YANLIS_TERIM", "Görev emri olan Defeat, ad biçimindeki 'Yenilgi' değil '-i yen' olarak çevrilmeli", True
    if (
        re.match(r"(?i)^\s*Kill\s+[^,!]", source)
        and re.match(r"(?iu)^\s*Öldür\s+", target)
    ):
        return "YAZIM_ANLAM_SUPHESI", "Kill görevi Türkçede hedef önce, '-i öldür' yüklemi sonda olacak biçimde yazılmalı", True
    if (
        re.match(r"(?i)^\s*(?:Get|Take)\b", source)
        and re.search(r"(?iu)^\s*Al şunu\.", target)
    ):
        return "YAZIM_ANLAM_SUPHESI", "Get/Take görevi bağlamsız 'Al şunu' kalıbına dönüşmüş", True
    if re.search(r"(?iu)\b(?:bir|için)\s+a\b", target):
        return "INGILIZCE_KALINTISI", "Belirsiz tanımlık 'a' bozuk İngilizce-Türkçe karışımı olarak kalmış", True
    if re.search(r"(?iu)\b(?:Experienceve|Hasarve|Eşyalar?ve|puanve|seviyeve)\b", target):
        return "YAZIM_ANLAM_SUPHESI", "İngilizce sözcük veya Türkçe bağlaç önceki sözcükle hatalı biçimde birleşmiş", True
    if re.search(r"(?i)\bMP\b", source) and re.search(r"(?iu)\bmilletvekili\b", target):
        return "YANLIS_TERIM", "Hareket Puanı kısaltması MP yanlışlıkla 'milletvekili' olarak çevrilmiş", True
    if re.search(r"(?i)\bstates?\b", source) and re.search(r"(?iu)\b(?:eyalet|devlet)\w*\b", target):
        return "YANLIS_TERIM", "Oyun mekaniğindeki state terimi coğrafi/siyasi bir ad değil, 'durum' olarak çevrilmeli", True
    if re.search(r"(?i)\bcast on\b", source) and re.search(r"(?iu)\bdevam et\b", target):
        return "YANLIS_TERIM", "Büyüyü hedef üzerinde kullanma ifadesi yanlışlıkla 'Devam et' olarak çevrilmiş", True
    if re.search(r"(?i)\bon a\b", source) and re.search(r"(?iu)\baçık a\b", target):
        return "YANLIS_TERIM", "'On a ...' hedef koşulu bozuk bir İngilizce-Türkçe karışımına dönüşmüş", True
    harvest_check_target = strip_protected_names(target, protected_names)
    if (
        re.search(r"(?i)\bharvest\w*\b", harvest_check_target)
        and target.strip() != source.strip()
    ):
        return "INGILIZCE_KALINTISI", "Hasat/toplama metninde çevrilmemiş Harvest kökü kaldı", True
    if (
        "dragoturkey" in source.casefold()
        and re.search(
            r"(?iu)dragotürkiye|drag\s+turk\w*|drag\s+turkey|dragot(?:uck|uğ|uş)\w*|"
            r"sürükleyici\s+hindi|atlı\s+hindi|\bhindi(?:'|y|n|ler|nin|yi|ye)",
            target,
        )
    ):
        return "YANLIS_TERIM", "Dragoturkey özel yaratık adı hindi/Türkiye olarak makine çevirisine uğramış", True
    if (
        re.search(
            r"(?i)\b(?:account|guild|house|manor|treasure|golden|large|big|hidden|locked|"
            r"mystery|reward|vault)\s+chests?\b|\bchests?\s+(?:locked|room|contains?|"
            r"contents?|capacity|slots?|rewards?|is\s+(?:empty|open|closed|locked))\b|"
            r"\b(?:open|unlock|find|search|access|examine|interact\s+with|remove\s+.+?\s+from|"
            r"deposit\s+.+?\s+in|take\s+.+?\s+from|get\s+.+?\s+from)\s+(?:the\s+|a\s+)?chests?\b",
            source,
        )
        and re.search(r"(?iu)\bgöğs", target)
    ):
        return "YANLIS_TERIM", "Depolama/hazine anlamındaki chest sözcüğü göğüs değil, sandık olmalı", True
    if re.search(r"(?i)recipes? for the (?:Handyman|Leather Dealer|Herbalist|Miner|Fisherman|Lumberjack|Trapper|Weapons Master) profession", source) and re.search(r"(?iu)\byemek tarifi\b", target):
        return "YANLIS_TERIM", "Zanaat üretim tarifleri yemek tarifi olarak çevrilmemeli", True
    if (
        re.search(r"(?i)(?:^|\\n)\s*Has\b", source)
        and "?" not in source
        and re.search(r"(?iu)\bvar mı\b", target)
    ):
        return "YAZIM_ANLAM_SUPHESI", "Kaynak bir sahiplik koşulu/bildirimi; soru biçiminde 'var mı' olarak çevrilmemeli", True
    if (
        "election finished" in source.casefold()
        and re.search(r"(?iu)\bvar mı\b", target)
    ):
        return "YAZIM_ANLAM_SUPHESI", "Seçim sonucu bildirimi yanlışlıkla soru biçimine çevrilmiş", True
    if re.search(r"(?i)\bHeals?\b", target) or re.search(r"(?i)Healsve", target):
        return "INGILIZCE_KALINTISI", "İyileştirme açıklamasında çevrilmemiş Heal/Heals sözcüğü kaldı", True
    gains_is_noun = bool(re.search(
        r"(?i)\b(?:extra|increased|all|armor|QB|AP|XP|experience|loot|harvesting)\s+gains\b|"
        r"\bgains\s+(?:are|were|have|from|with)\b|\bof\s+gains\b|\blosses\s+or\s+gains\b",
        source,
    ))
    if (
        re.search(r"(?i)\bgains\b", source)
        and not gains_is_noun
        and re.search(r"(?iu)\bkazanç(?:lar)?\b", target)
    ):
        return "YAZIM_ANLAM_SUPHESI", "Kaynakta fiil olan 'gains', Türkçede isim olan 'kazanç' biçiminde bırakılmış", True
    game_turn_source = re.search(
        r"(?i)\b(?:at (?:the )?(?:start|end) of (?:the |his |her |their |its |your )?turn|"
        r"start(?:s|ing)? (?:the |his |her |their |its |your )?turn|"
        r"end(?:s|ing)? (?:the |his |her |their |its |your )?turn|"
        r"per turn|each turn|every turn|current turn|next turn|odd turns?|even turns?)\b",
        source,
    )
    if game_turn_source and re.search(r"(?iu)\bdönüş(?:ü|ün|e|te|ten|ler|leri|lerde|lerden)?\b", target):
        return "YANLIS_TERIM", "Savaş sırasındaki turn terimi 'dönüş' değil 'tur' olarak çevrilmeli", True
    bad_turn_as_order = re.search(
        r"(?iu)\b(?:sıranın|sırasının|sıralarının)\s+(?:başında|başlangıcında|sonunda)\b|"
        r"\bsıra\s+başına\b|"
        r"\bsıra(?:sını|larını)\s+(?:başlat\w*|bitir\w*|sonlandır\w*|tamamla\w*)\b",
        target,
    )
    if game_turn_source and bad_turn_as_order:
        return "YANLIS_TERIM", "Savaş sırasındaki turn terimi sıra değil 'tur' olarak çevrilmeli", True
    declarative_when_source = re.match(
        r"(?i)^\s*When\s+(?!(?:is|are|was|were|did|do|does|will|would|can|could|should)\b)",
        source,
    )
    if declarative_when_source and re.match(r"(?iu)^\s*Ne zaman\b", target):
        return "YAZIM_ANLAM_SUPHESI", "Kaynak koşul/bildirim cümlesi Türkçede '... olduğunda/-dığında' yapısıyla çevrilmeli", True
    if key in NOX_REVIEWED_TRANSLATION_KEYS and target.strip():
        if not format_ok(source, target):
            return "BICIM_HATASI", "İnsan denetimli Nox çevirisinde biçim kodları kaynakla eşleşmiyor", True
        return "CEVRILDI", "İnsan denetimli Nox savaş mekaniği çevirisi", False
    if key in CLEAN_SOURCE_SEMANTIC_REPAIRS and target.strip():
        if not format_ok(source, target):
            return "BICIM_HATASI", "İnsan denetimli çeviride değişken, etiket veya koşul kodları kaynakla eşleşmiyor", True
        return "CEVRILDI", "Temiz İngilizce kaynaktan insan denetimli çeviri", False
    reviewed_v123 = SEMANTIC_EXACT_V123.get(key)
    if reviewed_v123 is None:
        reviewed_v123 = semantic_v123_translation(source)
    if reviewed_v123 == target and target.strip():
        if not format_ok(source, target):
            return "BICIM_HATASI", "V123 insan denetimli çeviride biçim kodları kaynakla eşleşmiyor", True
        return "CEVRILDI", "V123 semantik taramasında insan denetimli çeviri", False
    if MECHANIC_POINT_SOURCE_RE.search(source) and re.search(r"(?iu)\b(?:nokta\w*|skor\w*)\b", target):
        return "YANLIS_TERIM", "Oyun mekaniğindeki point/points terimi 'puan' olarak çevrilmeli", True
    if re.search(r"(?iu)(?:\[#\d+\]|\b\d+)\s+puanlar\b", target):
        return "YAZIM_ANLAM_SUPHESI", "Sayıdan sonra gereksiz çoğul kullanılmış; 'puan' olmalı", True
    if re.search(r"(?iu)\bpenaltiler\b", target):
        return "YANLIS_TERIM", "Penalty terimi Türkçede 'ceza' olarak çevrilmeli", True
    if re.search(r"(?i)\bsettle(?:d|s|ing)?\s+(?:the|a|your|our|their)?\s*scores?\b", source) and re.search(r"(?iu)\bskor", target):
        return "YANLIS_TERIM", "'Settle the score' deyimi skor değil, hesaplaşmak/hesabı kapatmak anlamındadır", True
    if re.search(r"(?iu)\b(?:calm\s+aşağı|again\b|well\s+evet|the\s+dragoturkey|finally\b)", target):
        return "INGILIZCE_KALINTISI", "Cümlede eski makine çevirisinden İngilizce-Türkçe karışımı kaldı", True
    if re.search(r"(?iu)\b(?:her\s+biri\s+[^,.!?:;]{0,35}\s+nokta|puanlar\s+kazandınız)\b", target):
        return "YAZIM_ANLAM_SUPHESI", "Puan ifadesinin Türkçe dil bilgisi bozuk", True
    if re.search(r"(?iu)\b(?:max|minimum|maximum)\s+\d+%?\s+bonus\b", target):
        return "INGILIZCE_KALINTISI", "Azami bonus ifadesi Türkçeleştirilmemiş", True
    if re.search(r"(?iu)(?:\bKategori\s*:|Oyunun genel metni için|\bidiomatic\b|bağlantılar değiştir)", target):
        return "MODEL_TALIMATI_SIZINTISI", "Çeviri yerine model talimatı veya işlem notu kaydedilmiş", True
    if key in {"scenes.pnj.base", "test.test.spellcheck", "zinit.barquette.04"}:
        return "TEKNIK_KORUNAN", "Dahili test/kod veya anlam taşımayan ses metni bilinçli olarak çevri dışında tutuldu", False
    if key == "quest.brume.timo.00.53" and target == source:
        return "TEKNIK_KORUNAN", "Kurgusal yaratık dili özgün biçimiyle korundu", False
    if re.search(r"(?iu)\b(?:monstrolar?|monstre|monsta)\b", target):
        return "YAZIM_ANLAM_SUPHESI", "Canavar terimi bozuk makine çevirisiyle yazılmış", True
    if re.search(r"(?iu)\bdönüş\s+(?:başına|sonunda|başlangıcında)\b", target) and re.search(r"(?i)\bturn\b", source):
        return "YAZIM_ANLAM_SUPHESI", "Turn sözcüğü tur yerine dönüş olarak çevrilmiş", True
    if re.search(r"(?iu)\b(?:heceler?|yazılımlar?)\b", target) and re.search(r"(?i)\bspells?\b", source):
        return "YANLIS_TERIM", "Spell sözcüğü yanlışlıkla hece/yazılım olarak çevrilmiş", True
    if re.search(r"(?iu)yazılım", target) and re.search(r"(?i)\brunes?\b", source):
        return "YANLIS_TERIM", "Rune sözcüğü rün yerine yazılım olarak çevrilmiş", True
    reviewed_lore_with_protected_names = {
        "chat.help",
        "quest.DD.cambriolage.rules.desc03",
        "companionBackgroundText.3084",
        "dial.comp.moine.02",
        "gelutin.dimension.gelax.03",
        "incarnam.ecosysteme.gargalou.endormissement",
        "inventory.transfer.items.popup",
        "OSAMODAS_SUMMON_COOLDOWNDescription",
        "prison.gelutin.exit",
        "quest.astrub.tonneauplante.rules.desc01",
        "quest.brume.cheptel.npc.05",
        "quest.brume.timo.00.07",
        "quest.ereboria.zone.03.09",
        "quest.nationch2.otomai.Cineflouqueux.PlayerId.01",
        "recycle",
        "content.13.268085",
        "content.13.380056",
        "content.16.14556",
        "content.16.19472",
        "content.16.19525",
        "content.16.19529",
        "content.4.6947",
        "content.4.4718",
        "content.9.7506",
        "content.9.9259",
        "content.9.9263",
        "content.16.6824",
        "content.16.9861",
        "content.16.10120",
        "content.16.11481",
        "content.16.13199",
        "content.16.14286",
        "content.16.15792",
        "content.16.16697",
        "content.16.17227",
        "content.16.18716",
        "content.16.18892",
        "content.16.20510",
        "content.16.23872",
        "content.16.23876",
        "content.16.23877",
        "content.16.24564",
        "content.16.24565",
        "content.16.26884",
        "content.16.28037",
        "content.16.28086",
        "content.16.28087",
        "content.16.28737",
        "content.16.29409",
        "content.16.30227",
        "content.16.30397",
        "content.16.30398",
        "content.16.30444",
        "content.16.32474",
        "content.16.32475",
        "content.16.32674",
        "content.16.33044",
        "content.24.-2010",
        "content.25.8940",
        "content.49.20040115",
        "content.49.20140051",
        "content.49.20140070",
        "content.60.20017",
        "content.63.5456",
        "content.64.2627",
        "content.64.4738",
        "content.64.4739",
        "content.64.6314",
        "content.67.148",
        "content.67.276",
        "content.67.416",
        "content.67.533",
        "content.67.575",
        "content.67.676",
        "content.67.692",
        "content.67.694",
        "content.67.699",
        "content.67.722",
        "content.67.787",
        "content.67.846",
        "content.67.849",
        "content.67.883",
        "content.67.940",
        "content.67.947",
        "content.67.951",
        "content.67.953",
        "content.67.958",
        "content.67.964",
        "content.67.968",
        "content.67.1014",
        "content.67.1015",
        "content.67.1016",
        "content.67.1063",
        "content.67.1066",
        "content.67.1121",
        "content.67.1152",
        "content.67.1154",
        "content.67.1218",
        "content.67.1219",
        "content.67.1222",
        "content.67.1234",
        "content.67.1239",
        "content.67.1261",
        "content.67.1269",
        "content.67.1270",
        "content.67.1272",
        "content.67.1273",
        "content.75.287",
        "content.75.836",
        "content.75.2026",
        "content.75.2136",
        "content.75.2175",
        "content.75.2184",
        "content.75.2185",
        "content.75.2191",
        "content.75.2212",
        "content.75.2230",
        "content.75.2232",
        "content.75.2233",
        "content.75.2235",
        "content.75.2263",
        "content.75.2272",
        "content.75.2273",
        "content.75.2274",
        "content.75.2275",
        "content.75.2276",
        "content.75.2333",
        "content.75.2368",
        "content.75.2375",
        "content.75.2377",
        "content.75.2385",
        "content.75.2526",
        "content.75.2546",
        "content.75.2600",
        "content.75.2720",
        "content.75.2729",
        "content.75.2820",
        "content.75.2919",
        "content.75.3094",
        "content.75.3103",
        "content.75.3150",
        "content.75.3176",
        "content.75.3177",
        "content.75.3184",
        "content.75.3186",
        "content.75.3207",
        "content.75.3278",
        "content.75.3280",
        "content.75.3293",
        "content.75.3305",
        "content.75.3338",
        "content.75.3360",
        "content.75.3385",
        "content.75.3466",
        "content.75.3468",
        "content.75.3474",
        "content.75.3477",
        "content.75.3508",
        "content.75.3584",
        "content.75.3630",
        "content.75.3734",
        "content.75.3804",
        "content.75.3903",
        "content.75.4111",
        "content.75.4117",
        "content.75.4127",
        "content.75.4241",
        "content.75.4274",
        "content.75.4352",
        "content.75.4405",
        "content.75.4409",
        "content.75.4427",
        "content.75.4454",
        "content.75.4459",
        "content.75.4531",
        "content.75.4649",
        "content.75.4655",
        "content.75.4712",
        "content.75.5100",
        "content.75.5117",
        "content.75.5169",
        "content.75.5272",
        "content.75.5287",
        "content.75.5338",
        "content.75.5359",
        "content.75.5376",
        "content.75.5413",
        "content.75.5431",
        "content.75.5530",
        "content.75.5550",
        "content.75.5559",
        "content.75.5609",
        "content.75.5632",
        "content.75.5779",
        "content.75.5785",
        "content.75.5821",
        "content.75.5822",
        "content.75.5823",
        "content.75.5828",
        "content.75.5833",
        "content.75.5834",
        "content.75.5835",
        "content.75.5843",
        "content.75.5845",
        "content.75.5846",
        "content.75.5848",
        "content.75.5850",
        "content.75.5851",
        "content.75.5859",
        "content.75.5862",
        "content.75.5864",
        "content.75.5865",
        "content.75.5870",
        "content.75.5873",
        "content.75.5879",
        "content.75.5881",
        "content.75.5883",
        "content.75.5884",
        "content.75.5935",
        "content.75.5948",
        "content.75.5968",
        "content.75.5970",
        "content.75.5972",
        "content.75.5973",
        "content.75.5975",
        "content.75.5979",
        "content.75.5980",
        "content.75.5983",
        "content.75.5987",
        "content.75.5989",
        "content.75.5990",
        "content.75.5991",
        "content.75.5995",
        "content.75.5998",
        "content.75.6003",
        "content.75.6005",
        "content.75.6006",
        "content.75.6009",
        "content.75.6010",
        "content.75.6011",
        "content.75.6012",
        "content.75.6014",
        "content.75.6018",
        "content.75.6023",
        "content.75.6024",
        "content.75.6025",
        "content.75.6027",
        "content.75.6028",
        "content.75.6033",
        "content.75.6034",
        "content.75.6035",
        "content.75.6036",
        "content.75.6042",
        "content.75.6046",
        "content.75.6078",
        "content.75.6087",
        "content.75.6089",
        "content.75.6090",
        "content.75.6091",
        "content.75.6092",
        "content.75.6093",
        "content.75.6094",
        "content.75.6105",
        "content.75.6107",
        "content.75.6111",
        "content.75.6112",
        "content.75.6113",
        "content.75.6121",
        "content.75.6146",
        "content.75.6165",
        "content.75.6166",
        "content.75.6207", "content.75.6231", "content.75.6237", "content.75.6238",
        "content.75.6239", "content.75.6247", "content.75.6287", "content.75.6328",
        "content.75.6350", "content.75.6355", "content.75.6440", "content.75.6477",
        "content.75.6498", "content.75.6520", "content.75.6527", "content.75.6564",
        "content.75.6569", "content.75.6570", "content.75.6571", "content.75.6616",
        "content.75.6617", "content.75.6620", "content.75.6626", "content.75.6630",
        "content.75.6655",
        "content.75.6682", "content.75.6697", "content.75.6717", "content.75.6718",
        "content.75.6760", "content.75.6822", "content.75.6862", "content.75.6873",
        "content.75.6902", "content.75.6937", "content.75.7011", "content.75.7018",
        "content.75.7143", "content.75.7144", "content.75.7166", "content.75.7197",
        "content.76.802", "content.76.1591", "content.76.2273", "content.76.3863",
        "content.76.3931", "content.76.3953", "content.76.3962", "content.76.4392",
        "content.76.5038",
        "content.76.5272", "content.76.5807", "content.76.6187", "content.76.6266",
        "content.76.6507", "content.76.8970", "content.76.9344", "content.76.11110",
        "content.76.13067", "content.76.13071", "content.76.13254", "content.76.13309",
        "content.76.13538", "content.76.13680", "content.76.14364", "content.76.14506",
        "content.76.14561", "content.76.14809", "content.76.14988", "content.94.203",
        "content.94.204", "content.94.211", "content.94.216", "content.94.220",
        "content.94.222",
        "content.94.240", "content.94.241", "content.94.429", "content.94.442",
        "content.120.5", "content.120.10", "content.123.60", "content.127.118",
        "content.132.22", "content.143.3", "content.149.6049", "content.156.5",
        "content.156.8", "content.156.28", "content.156.65", "content.156.142",
        "content.156.144", "content.156.194", "content.156.195", "content.156.202",
        "content.156.229", "content.156.271", "content.156.282", "content.156.312",
        "content.156.342", "content.156.346", "content.156.389", "content.156.414",
        "content.156.439", "content.156.462", "content.156.474", "content.156.533",
        "content.156.557", "content.156.558", "content.156.562", "content.156.567",
        "breedLongName.9", "calendar.timeNotice", "craft.frame.skillInfo",
        "craft.neededAtLevel", "desc.mru.skillRaffiner", "desc.stateDurationFinite",
        "exec.regen", "fight.ko", "harvest.action", "infoPop.death", "levelGain",
        "market.offer.search.result.count", "object", "pageNumber",
        "partyList.MemberDownscaledFormatedName", "partyList.MemberFormatedName",
        "quest.zinit.ch1.cine.otomai.antidote.25", "stasis.dungeon.turn",
        "content.13.347100", "content.33.345405", "content.33.401238",
        "content.60.20080",
        "INDIRECT_DMGShort", "INITShort", "INTELLIGENCEShort",
        "quest.huppermage.dortoirs.tutorial.title", "content.13.97659",
        "content.13.114232", "content.14.294", "content.25.17430",
        "content.25.17437", "content.25.17444", "content.25.17473",
        "content.25.17481", "content.26.-2055", "content.26.-2054",
        "content.26.-1984", "content.26.-1830", "content.26.-1663",
        "content.26.-1654", "content.64.2495", "content.64.2502",
        "content.64.4725", "content.64.9325", "content.64.11492",
        "content.67.708", "content.79.76", "content.156.29",
        "content.156.103",
        "content.24.-1657", "content.24.-1656", "content.24.-1655", "content.24.-1654",
        "content.67.445", "content.67.606", "content.67.609",
        "content.63.5343", "content.64.4412",
        "content.16.11107", "content.16.11108", "content.16.11109",
        "content.106.248", "content.156.6",
    }
    reviewed_lore_with_protected_names.update(CLEAN_SOURCE_SEMANTIC_REPAIRS)
    if key in reviewed_lore_with_protected_names and target.strip():
        if not format_ok(source, target):
            return "BICIM_HATASI", "Değişken, etiket veya koşul kodları kaynakla eşleşmiyor", True
        return "CEVRILDI", "İnsan denetimli çeviri; Wakfu büyü ve özel adları bilinçli korundu", False
    if key == "quest.chuchoku.04.06":
        return "TEKNIK_KORUNAN", "Karakter adıyla yapılan kısa hitap bilinçli korundu", False
    if key == "content.67.659" and target == source:
        return "TEKNIK_KORUNAN", "Ters yazılmış oyun içi bilmece özgün biçimiyle korundu", False
    if not reviewed_key and key.startswith("content.13.") and (
        re.match(r"^\s*\[se\](?:\s|$)", source, re.IGNORECASE)
        or re.match(r"^\s*-?\s*\[#\d+\]\s+(?:AP|WP|MP)(?:\s+\(.+\))?\s*$", source, re.IGNORECASE)
    ):
        return "KORUNAN_AD", "Yetenek/etki adı içeren teknik referans bilinçli korundu", False
    if is_reviewed_haven_translation(source, target):
        if not format_ok(source, target):
            return "BICIM_HATASI", "Sığınak terimi çevirisinde biçim kodları kaynakla eşleşmiyor", True
        return "CEVRILDI", "Haven terim ailesi insan denetimiyle Türkçeleştirildi", False
    if (
        not reviewed_key
        and (
            (is_protected_key(key) and not is_translatable_inventory_name(key, source))
            or protected_value
        )
    ):
        return "KORUNAN_AD", "Wakfu özel adı bilinçli olarak İngilizce tutuldu", False
    if len(re.findall(r"[A-Za-z]\w*\s*=\s*\[@[A-Za-z]\w*\]", source)) >= 2:
        return "TEKNIK_KORUNAN", "Geliştirici alan şeması ve teknik değişken listesi", False
    if key in {"content.33.313633", "content.33.345417"}:
        return "TEKNIK_KORUNAN", "Geliştirici konum/koşul deneme metni ve teknik sabitler", False
    if (
        (key.startswith("content.8.") and (
            source.startswith("[Dead]")
            or source.endswith(" Listening")
            or source.startswith("Listen ")
            or re.search(r"\(listening\)$", source, re.IGNORECASE)
            or source.endswith(" flag")
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+", source)
            or source == "perte de hp area_hp uand perte de hp"
            or source in {"Dranca/Safeport", "Safeport (CD)"}
        ))
        or (key.startswith("content.33.") and (
            source.startswith(("Clef simple Temple remove", "Clef boss Temple remove"))
            or source.startswith(("name = ", "nom : ", "PO min : "))
        ))
        or source in {
            "|]} LJo{¨:,", '[[#@`"_"à-]^@(ç_"-è@[]]{#\\|@~"\'-.',
            "Ponk Ponk Poiiiiiiink", "Poiiiiiiink Poink Poink", "ss", "a",
            "O34:D36-Aa1-A53", "Merah eht fo rood eht fo ebircs", "Élborrado",
            "Kralakralala Kralalalalalalove", "Drago{[1*]?girl:boy}",
            "{[1*]?Pretty:Handsome}", "Nox: [se]", "{[1*]?Ms.:Mr.} Smisse",
            "Jenry Hones Jr.", "test2"
        }
    ):
        return "TEKNIK_KORUNAN", "Dahili durum dinleyicisi, geliştirici anahtarı veya test metni", False
    if not target.strip():
        visible_source = visible_text(source).strip()
        if not re.search(r"[^\W\d_]", visible_source, re.UNICODE):
            return "TEKNIK_KORUNAN", "Yalnız oyun biçim kodlarından oluşan teknik kayıt", False
        if re.fullmatch(
            r"(?i)\s*-?\s*(?:AP|MP|WP|HP|PdV|PA|PM)(?:\s*[+\-*/:]?\s*\d*)?\s*",
            visible_source,
        ):
            return "TEKNIK_KORUNAN", "Kısa savaş değeri ve teknik mekanik etiketi", False
        # content.6 ve content.8 oyuncuya gösterilen etki/buff/durum adlarıdır.
        # Yukarıdaki dar dinleyici/test istisnaları dışında kısa olmaları onları
        # teknik metin yapmaz; boşlarsa gerçek çeviri eksiği olarak raporlanır.
        if key.startswith(("content.6.", "content.8.")):
            if re.fullmatch(r"(?i)\s*(?:test(?:\s*\d+)?|gameplay|basic container|removal)\s*", source):
                return "TEKNIK_KORUNAN", "Dahili buff/durum test etiketi", False
            return "EKSIK", "Oyuncuya gösterilen etki/buff/durum adı çevrilmemiş", True
        if key.startswith(VISIBLE_WORLD_LABEL_PREFIXES) and is_visible_world_text(source):
            if re.fullmatch(
                r"(?i)(?:test(?:\s+[a-z0-9]+)?|blabla|thdhdfhd|test puop|gsdgvdfgdfgdfre[.]{3})",
                source.strip(),
            ):
                return "TEKNIK_KORUNAN", "Dahili dünya etiketi veya geliştirici test metni", False
            return "EKSIK", "Oyuncuya gösterilen nesne/bölge/mekân adı çevrilmemiş", True
        if key.startswith("content.33."):
            mechanic_visible = visible_source.strip()
            if (
                re.fullmatch(r"(?i)[+\-\d\s]*(?:AP|MP|WP|HP|PdV|PA|PM)(?:\s+[A-Za-z]{1,3})?", mechanic_visible)
                or re.fullmatch(r"(?i)(?:test(?:\s*\d+)?|wip|ss|a|blah|flag|lol|biduule|bliblobla)", source.strip())
                or source.startswith(("Clef simple Temple remove", "Clef boss Temple remove", "name = ", "nom : ", "PO min : "))
                or len(re.findall(r"[A-Za-z]\w*\s*=\s*\[(?:#|@)?[A-Za-z]\w*\]", source)) >= 2
            ):
                return "TEKNIK_KORUNAN", "Dahili mekanik kodu, test etiketi veya kısa savaş değeri", False
            return "EKSIK", "Oyuncuya gösterilen kısa mekanik/etki etiketi çevrilmemiş", True
        if (
            re.fullmatch(r"(?i)\s*(?:Ping:\s*\[#\d+\]\s*ms|Test\s*\[#\d+\]/\[#\d+\]|\(PvP\)|Vic\./Def\.|Perso\s*\[#\d+\])\s*", source)
            or re.fullmatch(r"\s*\[#charac\s+(?:AP|MP|WP)\]\s*\[#\d+\]\s*(?:AP|MP|WP)\s*", source, re.IGNORECASE)
            or key.startswith(("hardware.test.", "key.test."))
            or re.fullmatch(r"[a-z]{8,}\.{0,3}", source)
            or re.fullmatch(r"(?i)(?:test\s+)?[a-z]{3,12}(?:\s+[a-z]{2,12})?", source)
            or source.strip() in {"Pizz'larva (normal)", "Somonone ulu mir touk."}
        ):
            return "TEKNIK_KORUNAN", "Teknik ölçüm, kısaltma, test metni veya oyun içi kod bilinçli korundu", False
        if re.search(r"(?i)(?:^|\.)(?:cinematic|cine|dialog|convo|live|parle)(?:\.|$)", key) and len(source) <= 48:
            return "TEKNIK_KORUNAN", "Kısa diyalog nidası, çağrı veya özel ad bilinçli korundu", False
        if len(source) <= 18 and (
            re.fullmatch(r"[A-Z][A-Za-zÀ-ž' -]*(?:!{1,3}|\.{3}|\?)?", source)
            or re.fullmatch(r"[A-Z0-9][A-Z0-9_.+/% -]{1,17}", source)
        ) and not ENGLISH_RE.search(source):
            return "TEKNIK_KORUNAN", "Kısa özel ad, kısaltma veya oyun içi ses bilinçli korundu", False
        if key.startswith(("content.47.", "content.76.")) and len(source) <= 48 and not ENGLISH_RE.search(source):
            return "TEKNIK_KORUNAN", "Diyalog nidası, yüz ifadesi veya özel haykırış bilinçli korundu", False
        if (
            re.match(r"^(https?://|www\.)", source)
            or not re.search(r"[^\W\d_]", source, re.UNICODE)
            or (len(source) <= 12 and re.fullmatch(r"[A-Z0-9_.+/% -]+", source))
        ):
            return "TEKNIK_KORUNAN", "Kısaltma, sayı, adres veya teknik kod", False
        return "EKSIK", "Çeviri üretilmemiş", True
    visible_source = visible_text(source).strip()
    letters = len(re.findall(r"[^\W\d_]", visible_source, re.UNICODE))
    if visible_source.startswith("Lorem ipsum dolor sit amet"):
        return "TEKNIK_KORUNAN", "Geliştirici yer tutucu metni özgün biçimiyle korundu", False
    if letters == 0 or re.fullmatch(r"[A-Z0-9_.+/% -]{1,12}", visible_source) or re.match(r"^(https?://|www\.)", visible_source):
        return "TEKNIK_KORUNAN", "Kısaltma, sayı, adres veya teknik kod", False
    if not format_ok(source, target):
        return "BICIM_HATASI", "Değişken, etiket veya koşul kodları kaynakla eşleşmiyor", True
    if target.strip() == source.strip():
        residue_without_names = strip_protected_names(source, protected_names)
        if not ENGLISH_RE.search(residue_without_names):
            return "TEKNIK_KORUNAN", "Özel ad, ünlem, ses veya Türkçede değişmeyen kısa ifade bilinçli korundu", False
        if (
            re.fullmatch(r"\s*(?:\[#\d+\]\s*)?(?:&(?:lt|gt);=?|[<>]=?)\s*(?:\[#\d+\])\s*", source)
            or re.fullmatch(r"(?i)\s*(?:HH:mm(?::ss)?|\d+v\d+|\[#\d+\][a-z]{0,2})\s*", source)
        ):
            return "TEKNIK_KORUNAN", "Karşılaştırma, saat, mesafe veya eşleşme biçimi bilinçli korundu", False
        if key.startswith(("content.47.", "content.76.")) and (
            re.fullmatch(r"\s*[:;=xXoOpPD()!?.\\/ -]+\s*", source)
            or re.fullmatch(r"(?i)\s*(?:ha\s*){2,}!+\s*", source)
            or (len(source) <= 16 and not ENGLISH_RE.search(source))
        ):
            return "TEKNIK_KORUNAN", "Diyalog yüz ifadesi, nida veya anlamsız ses bilinçli korundu", False
        return "INGILIZCE_KALDI", "Çevrilebilir metin İngilizceyle aynı kaldı", True
    if not complete(source, target):
        return "EKSIK_CUMLE", "Çeviri kaynağa göre aşırı kısa veya cümle atlanmış", True
    visible_target_for_quality = visible_text(target)
    repeated = re.search(r"(?iu)\b([^\W\d_]{2,})\b(?:[\s,;.!?-]+\1\b){4,}", visible_target_for_quality)
    if repeated:
        repeated_word = repeated.group(1)
        source_repetitions = len(re.findall(
            r"(?iu)(?<!\w)" + re.escape(repeated_word) + r"(?!\w)",
            visible_text(source),
        ))
        if source_repetitions < 4:
            return "YAZIM_ANLAM_SUPHESI", f"Aynı sözcük anormal biçimde tekrar ediyor: {repeated_word}", True
    if re.search(r"([\"'`])\1{7,}|(?:p>){4,}|ZXQ\d*QXZ|[əƏ]", visible_target_for_quality):
        return "YAZIM_ANLAM_SUPHESI", "Model tekrarı, bozuk yer tutucu veya Türkçe dışı karakter bulundu", True
    if re.match(r"(?i)^\s*Defeat\b", source) and not re.search(
        r"(?iu)\b(?:yen|yenilgiye\s+uğrat|mağlup\s+et)", target
    ):
        return "YAZIM_ANLAM_SUPHESI", "Görev hedefindeki 'Defeat' fiili Türkçe emir olarak çevrilmemiş", True
    if key.startswith(("content.63.", "content.64.")) and re.match(r"(?i)^\s*Kill\b", source):
        if re.match(r"(?iu)^\s*(?:Öldürmek|Öldürme|Öldürün)\b", target):
            return "YAZIM_ANLAM_SUPHESI", "Başarım hedefindeki 'Kill' fiili doğal Türkçe emir sırasına çevrilmemiş", True
        if not re.search(r"(?iu)\b(?:öldür\w*|yok\s+et|yen\w*)", target):
            return "YAZIM_ANLAM_SUPHESI", "Başarım hedefindeki 'Kill' eylemi çeviride kaybolmuş", True
    if key.startswith("content.64.") and re.match(r"(?i)^\s*(?:Talk|Speak)\s+to\b", source):
        if re.match(r"(?iu)^\s*Konuş\.", target) or not re.search(r"(?iu)\bkonuş", target):
            return "YAZIM_ANLAM_SUPHESI", "Konuşma hedefi doğal Türkçe söz dizimine çevrilmemiş", True
    achievement_bad = re.search(
        r"(?iu)^\s*(?:A ye\b|Oyuncular\s+\d+|Bitki\s+\d+|üretim\s+bir\b)|"
        r"yakınındaki\s+oteller|filmi\s+hakkında\s+ilgi\s+çekici\s+içerikler|"
        r"\bSktes\b|\bFace\s+En\b",
        target,
    )
    if key.startswith(("content.63.", "content.64.", "content.67.")) and achievement_bad:
        return "YAZIM_ANLAM_SUPHESI", f"Bozuk otomatik başarım çevirisi: {achievement_bad.group(0)}", True
    if re.search(r"Ã|Ä|Å|â€|�", target):
        return "KODLAMA_HATASI", "Bozuk karakter dizisi bulundu", True
    joined = joined_english_word(source, target, protected_names)
    if joined:
        return "BITISIK_INGILIZCE", f"İngilizce sözcük Türkçe ifadeye bitişmiş: {joined}", True
    bad = MISSPELLING_RE.search(target)
    if bad:
        return "YAZIM_ANLAM_SUPHESI", f"Şüpheli ifade: {bad.group(0)}", True
    bad_case = re.search(r"(?iu)\b[A-Za-zÇĞİÖŞÜçğıöşü]+(?:y?[ıiuü])\s+sahip\b", target)
    if bad_case:
        return "YAZIM_ANLAM_SUPHESI", f"Hatalı Türkçe hâl eki: {bad_case.group(0)}", True
    if "__WAKFU_" in target:
        return "BICIM_HATASI", "Model yer tutucusu çeviride kaldı", True
    if re.match(r"(?i)^\s*(translation|turkish|türkçe|çeviri|here is|işte)\s*:", target):
        return "MODEL_ACIKLAMASI", "Model yalnız çeviri yerine açıklama/etiket ekledi", True
    # Conditional grammar branches (for example M{[1*]?istress:aster}) are
    # engine syntax, not player-facing English. Remove the complete simple
    # conditional before looking for English residue in the visible target.
    residue_target = re.sub(r"\{\[[^\]]+\]\?[^{}]*\}", " ", target)
    target_without_known_names = strip_protected_names(visible_text(residue_target), protected_names)
    if re.search(r"(?iu)(?:^|[.!?]\s+|\\n\s*)The\s+[A-Za-z]", target_without_known_names):
        return "INGILIZCE_KALINTISI", "Cümlenin başında çevrilmemiş İngilizce 'The' kaldı", True
    visible_target = strip_probable_proper_names(target_without_known_names)
    english_hits = [hit.casefold() for hit in ENGLISH_RE.findall(visible_target)]
    # “the” can legitimately remain inside protected Wakfu titles such as
    # “Hark Saniss, the Last Giant”; the surrounding proper-name words are
    # removed above, leaving only this connector behind.
    if english_hits and not all(hit == "the" for hit in english_hits):
        return "INGILIZCE_KALINTISI", "Çeviri içinde yaygın İngilizce sözcük kaldı", True
    copied = copied_source_word(source, target, protected_names)
    if copied:
        return "INGILIZCE_KALINTISI", f"Kaynak sözcük çevrilmeden kaldı: {copied}", True
    return "CEVRILDI", "Biçim ve temel kalite denetimlerinden geçti", False


def terminology_problem(source, target, term_values):
    source_folded = source.casefold()
    target_folded = target.casefold()
    mandatory_terms = {
        "item", "items", "characteristics", "damage", "mastery", "rear mastery",
        "elemental mastery", "melee mastery", "distance mastery", "critical mastery",
        "healing mastery", "berserk mastery", "elemental resistance", "page", "level",
        "build", "default build", "rarity", "pockets", "unavailable", "mount zinit",
        "astrub fields", "astrub plains", "cania plains", "upper slope", "dor'mor cave",
    }
    for english, turkish in sorted(term_values.items(), key=lambda pair: len(pair[0]), reverse=True):
        english = str(english); turkish = str(turkish)
        english_folded = english.casefold()
        exact_source = source.strip().casefold() == english_folded
        if not exact_source and english_folded not in mandatory_terms:
            continue
        if len(english) < 4 or not turkish:
            continue
        if " " in english:
            present = english_folded in source_folded
        else:
            present = bool(re.search(r"(?<!\w)" + re.escape(english_folded) + r"(?!\w)", source_folded))
        if not present:
            continue
        # "Level" her bağlamda karakter seviyesi değildir. Grafik ayarındaki
        # "Level of Detail" Türkçede doğru olarak "Ayrıntı Düzeyi" olur;
        # "level up" ise bir fiildir ve terim sözlüğündeki isim karşılığını
        # zorlamak anlamı bozar.
        if english_folded == "level" and (
            "level of detail" in source_folded
            or re.search(r"(?<!\w)level(?:s|ed|ing)?\s+up(?!\w)", source_folded)
        ):
            continue
        # “Turn the page” bir deyimdir; Türkçede doğal karşılığı her zaman
        # “sayfa” sözcüğünü içermez.
        if english_folded == "page" and "turn the page" in source_folded and any(
            phrase in target_folded for phrase in ("geride bırak", "yeni bir başlangıç", "geçmişi kapat")
        ):
            continue
        required = turkish.casefold()
        # Terim cümle içinde Türkçe çoğul/iyelik/hal eki alabilir. Özellikle
        # "Özellikler" -> "Özellik sayfası" kullanımı hata değildir.
        stems = {required}
        stems.add(re.sub(r"(?:lar|ler)$", "", required))
        stems.add(re.sub(r"(?:ları|leri|lığı|liği|luğu|lüğü)$", "", required))
        # Turkish consonant softening and common inflected forms.
        stems.update({
            "nadirliğ" if english_folded == "rarity" else "",
            "element direnç" if english_folded == "elemental resistance" else "",
            "kullanılam" if english_folded == "unavailable" else "",
            "mevcut değil" if english_folded == "unavailable" else "",
            "müsait değil" if english_folded == "unavailable" else "",
            "erişilemez" if english_folded == "unavailable" else "",
            "özellik" if english_folded == "characteristics" else "",
            "ayırt edici" if english_folded == "characteristics" else "",
            "cep" if english_folded == "pockets" else "",
            "ceb" if english_folded == "pockets" else "",
            "düzey" if english_folded == "level" else "",
            "deneyimli" if english_folded == "level" else "",
            # Cümle içinde “damage” için “zarar” doğal ve doğru bir eş anlamlıdır;
            # tek başına arayüz etiketi yine sözlükteki “Hasar” karşılığını kullanır.
            "zarar" if english_folded == "damage" else "",
        })
        # “Su” ve “Al” gibi doğrulanmış kısa Türkçe karşılıklar da geçerlidir.
        stems = {stem for stem in stems if len(stem) >= 2}
        if (
            english_folded == "critical mastery"
            and "non-critical mastery" in source_folded
            and "kritik" in target_folded
            and "ustalık" in target_folded
        ):
            continue
        if not any(stem in target_folded for stem in stems):
            return f"Zorunlu Wakfu terimi eksik: {english} => {turkish}"
    return ""


def tsv(value):
    return str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def load_live_methods(path):
    latest = {}
    if not path or not Path(path).is_file():
        return latest
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            header = handle.readline().rstrip("\r\n").split("\t")
            indexes = {name: index for index, name in enumerate(header)}
            for line in handle:
                fields = line.rstrip("\r\n").split("\t")
                try:
                    if fields[indexes["Durum"]] != "KAYDEDILDI":
                        continue
                    key = fields[indexes["Anahtar"]]
                    latest[key] = {
                        "method": fields[indexes["Yontem"]],
                        "time": fields[indexes["Zaman"]],
                    }
                except (KeyError, IndexError):
                    continue
    except OSError:
        return {}
    return latest


def apply_phrase_rules(value, phrases):
    for old, new in phrases:
        pattern = r"(?<![\w])" + re.escape(old) + r"(?![\w])"
        value = re.sub(pattern, lambda _match, replacement=new: replacement, value)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-jar", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--terminology", required=True)
    parser.add_argument("--manual-repairs")
    parser.add_argument("--live-log")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--stage", required=True)
    args = parser.parse_args()

    translations = load_json(args.project, {})
    terminology = load_json(args.terminology, {})
    manual_path = (
        Path(args.manual_repairs)
        if args.manual_repairs
        else Path(args.project).with_name("manual_repairs_v23.json")
    )
    manual_repairs = load_json(manual_path, {}) if manual_path.exists() else {}
    term_keys = terminology.get("keys", {})
    term_values = terminology.get("values", {})
    term_phrases = sorted(terminology.get("phrases", {}).items(), key=lambda pair: len(pair[0]), reverse=True)
    term_keys.setdefault("content.15.0", "Yok")
    live_methods = load_live_methods(args.live_log)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / "Wakfu_Ceviri_Durum.tsv"
    issue_path = output / "Wakfu_Ceviri_Sorunlar.tsv"
    summary_path = output / "Wakfu_Ceviri_Ozet.txt"
    status_temp = status_path.with_suffix(status_path.suffix + ".tmp")
    issue_temp = issue_path.with_suffix(issue_path.suffix + ".tmp")
    header = "Anahtar\tKategori\tDurum\tYontem\tSon_Guncelleme\tIngilizce\tTurkce\tNeden\tBicim_OK\tButunluk_OK\n"
    counts = collections.Counter()
    total = 0
    issue_count = 0

    entries = list(read_properties(args.source_jar))
    spell_title_values = {
        source.strip()
        for key, source in entries
        if key.startswith("content.3.") and source.strip()
    }
    item_title_values = {
        source.strip()
        for key, source in entries
        if key.startswith("content.15.") and source.strip()
    }
    protected_values = {
        source.strip() for key, source in entries if is_protected_key(key) and source.strip()
    }
    protected_values.update(EXPLICIT_PROTECTED_NAMES)
    protected_name_lookup = protected_values | {value.casefold() for value in protected_values}

    with status_temp.open("w", encoding="utf-8-sig", newline="") as status_file, issue_temp.open("w", encoding="utf-8-sig", newline="") as issue_file:
        status_file.write(header)
        issue_file.write(header)
        for key, source in entries:
            total += 1
            linked_skill_name = (
                key.startswith(("content.6.", "content.8.", "content.33."))
                and source.strip() in spell_title_values
            )
            linked_item_name = (
                key.startswith(LINKED_ITEM_PREFIXES)
                and source.strip() in item_title_values
            )
            forced_item_name = (
                key.startswith("content.15.")
                and not is_translatable_inventory_name(key, source)
            )
            forced_original_combat_name = (
                (
                    key.startswith(("content.3.", "content.8.", "content.15."))
                    and key not in REVIEWED_TRANSLATABLE_NAME_KEYS
                )
                or key == "content.6.1049"
            )
            protected_value = linked_skill_name or source.strip() in protected_values
            # Aynı İngilizce değer gerçek bir eşya/NPC adında geçse bile
            # arayüz, açıklama, görev ve diyalog alanını kilitleme. Ana
            # programdaki Test-IsProtectedNameKey kuralıyla aynı davranış.
            if (
                protected_value
                and not linked_skill_name
                and not linked_item_name
                and source.strip() not in EXPLICIT_PROTECTED_NAMES
                and category(key) in {
                "ARAYUZ", "GENEL_OYUN_METNI", "MEKANIK_BUFF_ACIKLAMA",
                "GOREV_HEDEF", "DIYALOG_HIKAYE", "REHBER_EGITIM",
                "ESYA_ACIKLAMA", "PAZAR_TICARET", "TEKNIK_ETKI_KALIBI",
                "WAKFU_OZEL_ADI", "WAKFU_UNVAN_ADI",
                "NPC_ETKILESIM_MEKAN_ADI", "GOREV_ETKINLIK_OZEL_ADI",
                "BASARIM_KATEGORISI", "BASARIM_ADI",
                "YETENEK_ETKI_ADI", "BUFF_DURUM_ADI",
                }
            ):
                protected_value = False
            translatable_inventory_name = is_translatable_inventory_name(key, source)
            if translatable_inventory_name:
                protected_value = False
            protected_key = (
                linked_skill_name
                or linked_item_name
                or (is_protected_key(key) and not translatable_inventory_name)
            )
            # Anahtar bazındaki insan onaylı karşılıklar özel-ad ailesinde olsa
            # bile kaynak İngilizceye geri düşmemelidir. Bu aynı zamanda audit,
            # ana program, statik JAR ve güncellemeye uyarlanan setup çıktısının
            # aynı öncelik sırasını kullanmasını sağlar.
            forced_term_key = key in term_keys
            forced_term_value = (
                source in term_values
                and not (linked_skill_name or linked_item_name or forced_item_name)
                and key.startswith(VISIBLE_WORLD_LABEL_PREFIXES)
            )
            reviewed_haven_translation = (
                key in translations
                and is_reviewed_haven_translation(source, str(translations[key]))
            )
            if linked_skill_name:
                target = source
                provider = "ORIJINAL_BAGLANTILI_YETENEK_ADI"
            elif linked_item_name:
                target = source
                provider = "ORIJINAL_BAGLANTILI_ESYA_ADI"
            elif forced_original_combat_name:
                target = source
                provider = "ORIJINAL_SAVAS_DURUMU_ADI"
            elif forced_item_name:
                target = source
                provider = "ORIJINAL_WAKFU_ADI"
            elif key in manual_repairs:
                target = str(manual_repairs[key])
                provider = "ELLE_DOGRULANMIS_DUZELTME"
            elif key in translations:
                target = str(translations[key])
                provider = live_methods.get(key, {}).get("method", "CEVIRI_BELLEGI")
            elif forced_term_key:
                target = str(term_keys[key])
                provider = "TERIM_ANAHTARI"
            elif forced_term_value:
                target = str(term_values[source])
                provider = "TERIM_SOZLUGU"
            elif key in MANUAL_PROTECTED_TRANSLATION_KEYS and key in translations:
                target = str(translations[key])
                provider = "ELLE_DOGRULANMIS_KORUNAN_ACIKLAMA"
            elif reviewed_haven_translation:
                target = str(translations[key])
                provider = "ELLE_DOGRULANMIS_HAVEN_TERIMI"
            elif protected_key or protected_value:
                target = source
                provider = "ORIJINAL_WAKFU_ADI"
            elif source in term_values:
                target = str(term_values[source])
                provider = "TERIM_SOZLUGU"
            else:
                target = ""
                provider = "YOK"
            # Anahtar/değer bazındaki insan denetimli sözlük sonucu kesindir;
            # bağlamsız toplu ifade kuralları onun üzerine uygulanmaz.
            if target and provider == "CEVIRI_BELLEGI":
                target = apply_phrase_rules(target, term_phrases)
            status, reason, issue = analyze(
                key,
                source,
                target,
                False if (forced_term_key or forced_term_value) else protected_value,
                protected_name_lookup,
                reviewed_key=(
                    False
                    if (
                        linked_skill_name
                        or linked_item_name
                        or forced_item_name
                        or forced_original_combat_name
                    )
                    else (
                        (key in manual_repairs or forced_term_key or forced_term_value)
                        and not (
                            key in TRANSLATABLE_QUEST_ITEM_COLLISION_KEYS
                            and target.strip() == source.strip()
                        )
                    )
                ),
                trusted_translation=(provider == "ELLE_DOGRULANMIS_DUZELTME"),
            )
            if provider == "TERIM_SOZLUGU" and target.strip() == source.strip():
                status, reason, issue = "CEVRILDI", "Terim Türkçede de aynı yazılır", False
            if (
                not issue
                and status not in {"KORUNAN_AD", "TEKNIK_KORUNAN"}
                and not key.startswith(("content.6.", "content.8."))
                and not (
                    (protected_key or protected_value)
                    and not (key in manual_repairs or forced_term_key)
                )
            ) and provider != "ELLE_DOGRULANMIS_DUZELTME":
                term_issue = terminology_problem(source, target, term_values)
                if term_issue:
                    status, reason, issue = "TERIM_HATASI", term_issue, True
            updated_at = live_methods.get(key, {}).get("time", "")
            counts[status] += 1
            row = "\t".join(tsv(value) for value in (
                key, category(key), status, provider, updated_at, source, target, reason,
                str(format_ok(source, target)), str(complete(source, target)),
            )) + "\n"
            status_file.write(row)
            if issue:
                issue_file.write(row)
                issue_count += 1
    os.replace(status_temp, status_path)
    os.replace(issue_temp, issue_path)

    summary = [
        "WAKFU TÜRKÇE ÇEVİRİ DURUMU",
        f"Aşama: {args.stage}",
        # Rapor kullanıcıya bilgisayarın yerel duvar saatiyle gösterilir.
        f"Tarih: {datetime.now():%Y-%m-%d %H:%M:%S}",  # noqa: DTZ005
        f"Toplam metin: {total}",
        f"İncelenmesi gereken: {issue_count}",
        "",
    ]
    summary.extend(f"{name}: {counts[name]}" for name in sorted(counts))
    summary.extend((
        "", f"Tüm satırlar: {status_path}", f"Sorunlu/eksik satırlar: {issue_path}",
        f"Olay ve hata günlüğü: {output / 'Wakfu_Ceviri_Log.txt'}",
    ))
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8-sig")
    print(f"AUDIT|{total}|{issue_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
