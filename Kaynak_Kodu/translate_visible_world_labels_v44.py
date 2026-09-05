#!/usr/bin/env python3
"""Translate hidden player-facing WAKFU object, zone and location labels."""

from __future__ import annotations

import argparse
import collections
import json
import re
import time
from pathlib import Path

from translate_visible_states_v44 import (
    INTERNAL_RE,
    format_tokens,
    load_json,
    protect_text,
    protected_terms,
    save_json,
    source_values,
    translate_batch,
)


VISIBLE_PREFIXES = (
    "content.54.", "content.59.", "content.66.", "content.77.",
    "content.78.", "content.79.", "content.81.", "content.82.",
    "content.83.", "content.88.", "content.89.", "content.93.",
    "content.96.", "content.106.", "content.122.", "content.124.",
    "content.126.", "content.137.", "content.140.", "content.151.",
    "content.155.", "content.158.", "content.161.",
)
WORLD_INTERNAL_RE = re.compile(
    r"(?i)^(?:test(?:\s+[a-z0-9]+)?|blabla|thdhdfhd|test puop|"
    r"gsdgvdfgdfgdfre[.]{3})$"
)
WORLD_DESCRIPTOR_RE = re.compile(
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
WORLD_GENERIC_SINGLE = {
    "alley", "altar", "attic", "bank", "basement", "bed", "bridge",
    "camp", "cave", "center", "chamber", "clinic", "cube", "desk",
    "disco", "dock", "door", "downstairs", "east", "entrance", "exit",
    "factory", "farm", "field", "fountain", "gate", "grave", "hall",
    "inn", "ladder", "library", "market", "mine", "north", "office",
    "park", "platform", "port", "prison", "refuge", "restaurant", "road",
    "roof", "room", "ruins", "school", "sewers", "shore", "south",
    "stairs", "station", "store", "temple", "tomb", "tower", "tunnel",
    "underground", "upstairs", "village", "warehouse", "west", "workshop",
}
WORLD_PROTECTED_TERMS = {
    "Amakna", "Bonta", "Brakmar", "Sufokia", "Astrub", "Incarnam",
    "Dragoturkey", "Drago-Express", "Wabbit", "Cawwot", "Gobball", "Tofu",
    "Crocodyl", "Bwork", "Riktus", "Shushu", "Dofus", "Wakfu", "Stasis",
    "Zaap", "Canoon", "Moon-Canoon", "Huppermage", "Foggernaut", "Sadida",
    "Xelor", "Enutrof", "Ecaflip", "Eliotrope", "Eliatrope", "Osamodas",
    "Ouginak", "Pandawa", "Sacrier", "Masqueraider", "Eniripsa", "Sram",
    "Rogue", "Feca", "Cra", "Iop", "Shhhudoku",
}


def is_visible_world_text(source: str) -> bool:
    """Separate translatable labels/signs from bare WAKFU proper names."""
    shown = re.sub(r"<[^>]+>", " ", source.replace("\\n", " "))
    words = re.findall(r"[A-Za-zÀ-ž][A-Za-zÀ-ž'’-]*", shown)
    if source in MANUAL or source.strip().casefold() in WORLD_GENERIC_SINGLE:
        return True
    if WORLD_DESCRIPTOR_RE.search(shown):
        return True
    lower_starts = sum(word[:1].islower() for word in words)
    if len(words) >= 4 and lower_starts >= 2 and (
        "\\n" in source or "<" in source or re.search(r"[.!?;:]", source)
    ):
        return True
    if len(words) >= 7 and lower_starts >= 3:
        return True
    return False

MANUAL = {
    "\"Amakna:\\nhome is where the hearth is.\"": "\"Amakna:\\nyuva, ocağın olduğu yerdir.\"",
    "<b>Hugh the little shepherd</b\"For young <b>trappers</b> bursting with energy.\"": "<b>Küçük çoban Hugh</b\"İçi enerji dolu genç <b>tuzakçılar</b> için.\"",
    "<b>Trapper with Hugo Bello</b>\\n\"Be a <b>trapper</b>, whippersnapper.\"": "<b>Hugo Bello ile tuzakçılık</b>\\n\"Haydi genç, <b>tuzakçı</b> ol.\"",
    "\"Save the animals, become a <b>trapper</b>\\nbecause they're not just for Christmas.\"": "\"Hayvanları koru, <b>tuzakçı</b> ol;\\nçünkü onlar yalnızca Noel zamanı yaşamıyor.\"",
    "<b>Trapper</b>\\n\"Nothing says 'I love you' better.\"": "<b>Tuzakçı</b>\\n\"Hiçbir şey 'Seni seviyorum' demenin yerini tutamaz.\"",
    "<b>Trapping with Monty Bello</b>\\n\"Be a <b>trapper,</b> whippersnapper.\"": "<b>Monty Bello ile tuzakçılık</b>\\n\"Haydi genç, <b>tuzakçı</b> ol.\"",
    "<b>Brakmar</b>\\n\"Where biff-bang-wallop wins every time\"": "<b>Brakmar</b>\\n\"Patırtı kütürtünün hep kazandığı yer\"",
    "<text align=\"center\">Ci-gît\\nle Père Turban\\naussi intriguant\\nque bon derviche</text>": "<text align=\"center\">Burada yatar\\nTurban Baba;\\nne kadar gizemliyse\\no kadar iyi bir dervişti.</text>",
    "Stuffed Dragoturkey": "Doldurulmuş Dragoturkey",
    "Singing Fields North - Dirty Trouffe": "Şarkı Tarlaları Kuzey - Dirty Trouffe",
    "Bwork Foot Room": "Bwork Ayak Odası",
    "Bwork Dungeon": "Bwork Zindanı",
    "Bwork Temple": "Bwork Tapınağı",
    "Srambad Inn": "Srambad Hanı",
    "Dock": "İskele",
    "Bontarian Inn": "Bonta Hanı",
    "Sufokian Inn": "Sufokia Hanı",
    "Caelius' House": "Caelius'un Evi",
    "Calamari's Hideout": "Calamari'nin Sığınağı",
    "Caca Chonel Street": "Caca Chonel Sokağı",
    "Arena": "Arena",
    "Bubourg Warehouse": "Bubourg Deposu",
    "Crackler Dungeon": "Crackler Zindanı",
    "Shhhudoku Kingdom": "Shhhudoku Krallığı",
    "Amakna Galleries Drago-Express": "Amakna Galerileri Drago-Express",
    "Sufokia Galleries Drago-Express": "Sufokia Galerileri Drago-Express",
    "Bonta Galleries Drago-Express": "Bonta Galerileri Drago-Express",
    "Brakmar Galleries Drago-Express": "Brakmar Galerileri Drago-Express",
    "[Royal Gobball] Entry -> Room 1": "[Royal Gobball] Giriş -> Oda 1",
    "[Royal Gobball] Room 1 -> Room 2": "[Royal Gobball] Oda 1 -> Oda 2",
    "[Royal Gobball] Room 2 -> BOSS": "[Royal Gobball] Oda 2 -> BOSS",
    "[Royal Gobball] BOSS -> Exit": "[Royal Gobball] BOSS -> Çıkış",
    "[Royal Gobball] Shed Exit": "[Royal Gobball] Kulübe Çıkışı",
    "Condemned Seed Storeroom": "Mühürlü Tohum Deposu",
    "Entrance to the Time Rift": "Zaman Yarığı Girişi",
    "Past Time Rift": "Geçmiş Zaman Yarığı",
    "Present Time Rift": "Şimdiki Zaman Yarığı",
    "Fertile Prairie - East": "Verimli Çayır - Doğu",
    "Fertile Prairie - West": "Verimli Çayır - Batı",
    "Hugo's Prairie Drago-Express": "Hugo'nun Çayırı Drago-Express",
    "Monty's Prairie": "Monty'nin Çayırı",
    "Monty's Prairie Drago-Express": "Monty'nin Çayırı Drago-Express",
    "Trapper's Prairie": "Tuzakçının Çayırı",
    "Humid Den": "Nemli İn",
    "Leave the Tower": "Kuleden Ayrıl",
    "Miss Ugly Tower\\nUgly people only": "Miss Ugly Kulesi\\nYalnızca çirkinler",
    "Neo Ship Wreckage": "Neo Gemi Enkazı",
    "Ohwymi - Castuc Grove Outbound": "Ohwymi - Castuc Korusu Çıkışı",
    "Sadida Kingdom - Deforested Forest": "Sadida Krallığı - Ormansızlaştırılmış Orman",
    "The Three Pistes' Cave Drago-Express": "Three Pistes Mağarası Drago-Express",
    "Three Pistes' Cave Drago-Express": "Three Pistes Mağarası Drago-Express",
    "Those without brains take the <b>boat</b>.": "Beyni olmayanlar <b>tekneye</b> biner.",
    "<b>Crusty Road</b>\\n\"When needs crust.\"": "<b>Kabuklu Yol</b>\\n\"Kabuğa ihtiyaç olduğunda.\"",
    "<b>Crusty Road</b>\\n\"Where the wheat's cheap.\"": "<b>Kabuklu Yol</b>\\n\"Buğdayın ucuz olduğu yer.\"",
    "<b>The Three Pistes' Cave</b>\\n\"Your stomach loves the work they do here.\"": "<b>Three Pistes Mağarası</b>\\n\"Miden burada yapılan işi sevecek.\"",
    "<b>Kelba market</b>\\n\"Buy more to spend more!\"": "<b>Kelba Pazarı</b>\\n\"Daha çok harcamak için daha çok satın al!\"",
    "Gnarled Barklee's Forest": "Gnarled Barklee'nin Ormanı",
    "Captain Calamari's Secret Hideout": "Captain Calamari'nin Gizli Sığınağı",
    "The Black Crow's Lair": "Black Crow'un İni",
    "The Black Crow's Alley": "Black Crow Sokağı",
    "Black Crow's Alley": "Black Crow Sokağı",
    "Neo Black Crow's Lair": "Neo Black Crow'un İni",
    "Antechamber of the Black Crow's Lair": "Black Crow İni'nin Ön Odası",
    "Dungeon of the Black Crow's Lair": "Black Crow İni Zindanı",
    "Locker of the Black Crow's Lair": "Black Crow İni'nin Dolabı",
    "Nanny Larva's Lair": "Nanny Larva'nın İni",
    "E.Z. Yeast's Kitchen": "E.Z. Yeast'in Mutfağı",
    "Koko the Nutt's Lair": "Koko the Nutt'ın İni",
    "Dragon Pig Territory": "Dragon Pig Bölgesi",
    "Dragon Pig Island": "Dragon Pig Adası",
    "Dragon Pig's Lair Drago-Express": "Dragon Pig'in İni Drago-Express",
    "Charles-Henri of Vileardent's Office": "Charles-Henri of Vileardent'ın Ofisi",
    "Grand Orrok's Warehouse": "Grand Orrok'un Deposu",
    "Temple of the Grand Orrok": "Grand Orrok Tapınağı",
    "Octopus Crew Dungeon": "Octopus Crew Zindanı",
    "Bworkana Clan Dungeon": "Bworkana Clan Zindanı",
    "Bwork Chief's Quarters": "Bwork Chief'in Odası",
    "Bwork Chief Quarters": "Bwork Chief'in Odası",
    "Mineral Tower": "Mineral Kulesi",
    "The Mineral Tower": "Mineral Kulesi",
    "Mineral Tower Entrance": "Mineral Kulesi Girişi",
    "Mineral Tower Exterior": "Mineral Kulesi Dışı",
    "Dimensional Voyager's Headquarters": "Boyut Gezgini'nin Karargâhı",
    "Cult HQ": "Tarikat Karargâhı",
    "Ogrest's Cult Headquarters": "Ogrest Tarikatı Karargâhı",
    "UGW Headquarters": "UGW Karargâhı",
    "Neo HQ": "Neo Karargâhı",
    "Amakna Headquarters": "Amakna Karargâhı",
    "Bonta Headquarters": "Bonta Karargâhı",
    "Black Wabbit Headquarters": "Black Wabbit Karargâhı",
    "Vigilante School - To the Haven World": "Vigilante Okulu - Sığınak Dünyası'na",
    "Canoon of the Guard toward Headquarters": "Karargâha Giden Muhafız Canoon'u",
    "Black Wabbit Dungeon Drago-Express": "Black Wabbit Zindanı Drago-Express",
    "Celestial Gobball Dungeon Drago-Express": "Celestial Gobball Zindanı Drago-Express",
    "Celestial Tofu Dungeon Drago-Express": "Celestial Tofu Zindanı Drago-Express",
    "Puddly Dungeon Drago-Express": "Puddly Zindanı Drago-Express",
    "Magik Riktus Den Drago-Express": "Magik Riktus İni Drago-Express",
    "Miss Ugly Tower Drago-Express": "Miss Ugly Kulesi Drago-Express",
    "Kelba Market Drago-Express": "Kelba Pazarı Drago-Express",
    "Mr. M's Lands Drago-Express": "Mr. M'nin Toprakları Drago-Express",
    "The Black Crow's Lair Drago-Express": "Black Crow'un İni Drago-Express",
    "The Black Crow's Peak Drago-Express": "Black Crow Zirvesi Drago-Express",
    "<b>The Black Crow</b>\\n\"He's hated for a reason.\"": "<b>Black Crow</b>\\n\"Boşuna nefret edilmiyor.\"",
    "\"Every day without an attack\\nis a victory over the <b>Black Crow</b>.\"": "\"Saldırısız geçen her gün,\\n<b>Black Crow</b>'a karşı kazanılmış bir zaferdir.\"",
    "<b>Lumberjack work with Gnarled Barklee</b>\\n\"He's your bloak!\"": "<b>Gnarled Barklee ile odunculuk</b>\\n\"Aradığın kütük onda!\"",
    "Barrel": "Fıçı",
    "Lever": "Kol",
    "Minecart": "Maden Arabası",
    "Storeroom Door": "Depo Kapısı",
    "Rudder": "Dümen",
    "Stele": "Dikilitaş",
    "Cauldron": "Kazan",
    "Platform": "Platform",
    "Anvil": "Örs",
    "Boat": "Tekne",
    "Stairs": "Merdiven",
    "Book": "Kitap",
    "Bridge": "Köprü",
    "Wall": "Duvar",
    "Rock": "Kaya",
    "Trap": "Tuzak",
    "Generator": "Jeneratör",
    "Pillar": "Sütun",
    "Tombstone": "Mezar Taşı",
    "Unknown Island": "Bilinmeyen Ada",
    "Sadida Kingdom": "Sadida Krallığı",
    "Wheelbarrow": "El Arabası",
    "Lawn Roller": "Çim Silindiri",
    "Wooden Door": "Ahşap Kapı",
    "Wooden Fencing": "Ahşap Çit",
    "Drinking Trough": "Suluk",
    "Abandoned Mine": "Terk Edilmiş Maden",
    "South Beach": "Güney Sahili",
    "Astrub Mountains": "Astrub Dağları",
    "Astrub Crypts": "Astrub Mahzenleri",
    "Incarnam Dungeon": "Incarnam Zindanı",
    "Neighborhood": "Mahalle",
    "Bermuda Triangle": "Bermuda Üçgeni",
    "Restaurant": "Restoran",
    "Coin House": "Kama Evi",
    "Featherweight": "Tüy Sıklet",
    "Heavyweight": "Ağır Sıklet",
    "Colossal": "Devasa",
    "Crushing": "Ezici",
    "Stool": "Tabure",
    "Celestial Prairies": "Göksel Çayırlar",
    "Three Pistes' Cave": "Three Pistes Mağarası",
    "Miss Ugly Tower": "Miss Ugly Kulesi",
    "Tsu's Palace": "Tsu'nun Sarayı",
    "Sidimote Moors": "Sidimote Bataklıkları",
    "Schnek Den": "Schnek İni",
    "Sandy Cawwot": "Kumlu Cawwot",
    "Bonta Riktus Den": "Bonta Riktus İni",
    "Brakmar Riktus Den": "Brakmar Riktus İni",
    "Sufokia Riktus Den": "Sufokia Riktus İni",
    "Kwismas Snow": "Kwismas Karı",
    "Mangeoire": "Yemlik",
    "Hugo's Prairie": "Hugo'nun Çayırı",
    "Stoodeep Mines": "Stoodeep Madenleri",
    "Cwab's Castle": "Cwab'ın Kalesi",
    "Crocodyl Dungeon": "Crocodyl Zindanı",
    "Void Spiral": "Boşluk Sarmalı",
    "Misty Isle": "Sisli Ada",
    "Iced-Over Crest": "Donmuş Sırt",
    "Steamulating Shore": "Steamulating Sahili",
    "Crusty Road": "Kabuklu Yol",
    "Gutted Plaza": "Harap Meydan",
    "Feverish Depths": "Hummalı Derinlikler",
    "Moon-Canoon": "Moon-Canoon",
    "Canoon": "Canoon",
    "Wabbit Totem": "Wabbit Totemi",
    "Pizz'larva (normal)": "Pizz'larva (normal)",
    "Switch": "Şalter",
    "Safe": "Kasa",
    "Piston": "Piston",
    "Rushu": "Rushu",
    "Toross": "Toross",
    "Dementya": "Dementya",
    "Katas": "Katas",
    "Mimic": "Taklitçi",
    "Moon": "Moon",
    "Ratatombs": "Sıçan Mezarları",
    "Three": "Üç",
    "Fairyworks": "Peri Fişekleri",
    "Dorsum": "Sırt",
    "Survival": "Hayatta Kalma",
    "Sedentary": "Hareketsiz",
    "Tremblor": "Sarsıntı",
    "Manhunt": "İnsan Avı",
    "Torment": "Eziyet",
    "Tripled": "Üçe Katlandı",
    "Doubled": "İkiye Katlandı",
    "Symbiote": "Simbiyot",
    "Stasilizer": "Stasisleyici",
    "Campfire": "Kamp Ateşi",
    "Stalagmite": "Dikit",
    "Puffball": "Puf Topu",
    "Wheeturn": "Dönence",
    "Strawbale": "Saman Balyası",
    "Furrower": "Karık Açıcı",
    "Basin": "Havuz",
    "Feeder": "Yemlik",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    data_dir = root / "Ceviri_Verileri"
    report_dir = root / "Raporlar"
    sources = source_values(root / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar")
    project_path = data_dir / "wakfu_tr_ceviri.json"
    manual_path = data_dir / "manual_repairs_v23.json"
    project = load_json(project_path)
    manual = load_json(manual_path)
    cache_path = report_dir / "Wakfu_Dunya_Etiketi_Ceviri_Onbellek_v44.json"
    cache = load_json(cache_path)
    names = sorted(
        set(protected_terms(sources)) | WORLD_PROTECTED_TERMS,
        key=lambda item: (-len(item), item),
    )
    official_names = {
        source.strip()
        for key, source in sources.items()
        if key.startswith(("content.3.", "content.15.")) and source.strip()
    }

    reuse_candidates: dict[str, set[str]] = collections.defaultdict(set)
    for key, source in sources.items():
        existing = manual.get(key, project.get(key, "")).strip()
        if existing and existing != source.strip() and format_tokens(source) == format_tokens(existing):
            reuse_candidates[source].add(existing)
    reusable = {
        source: next(iter(values))
        for source, values in reuse_candidates.items()
        if len(values) == 1
    }

    targets: dict[str, str] = {}
    skipped_internal = 0
    skipped_proper = 0
    skipped_item_reference = 0
    for key, source in sources.items():
        if not key.startswith(VISIBLE_PREFIXES):
            continue
        if project.get(key, "").strip() or manual.get(key, "").strip():
            continue
        if not is_visible_world_text(source):
            skipped_proper += 1
            continue
        if (
            INTERNAL_RE.search(source.strip())
            or WORLD_INTERNAL_RE.fullmatch(source.strip())
            or not re.search(r"[A-Za-z]", source)
        ):
            skipped_internal += 1
            continue
        targets[key] = source

    unique_sources = sorted(set(targets.values()))
    results = dict(reusable)
    results.update(cache)
    results.update(MANUAL)
    pending = [source for source in unique_sources if source not in results]
    print(json.dumps({
        "target_keys": len(targets), "unique_sources": len(unique_sources),
        "pending": len(pending), "skipped_internal": skipped_internal,
        "skipped_proper": skipped_proper,
        "skipped_item_reference": skipped_item_reference,
    }, ensure_ascii=False), flush=True)

    batches: list[list[tuple[str, str, dict[str, str]]]] = []
    batch: list[tuple[str, str, dict[str, str]]] = []
    batch_chars = 0
    for source in pending:
        protected, replacements = protect_text(
            source, [] if source.strip() in official_names else names
        )
        if batch and (len(batch) >= 20 or batch_chars + len(protected) > 1400):
            batches.append(batch)
            batch, batch_chars = [], 0
        batch.append((source, protected, replacements))
        batch_chars += len(protected) + 1
    if batch:
        batches.append(batch)

    for index, items in enumerate(batches, 1):
        results.update(translate_batch(items))
        if index % 10 == 0 or index == len(batches):
            cache_snapshot = dict(cache)
            cache_snapshot.update({source: results[source] for source in unique_sources if source in results})
            save_json(cache_path, cache_snapshot)
            print(f"PROGRESS|{index}|{len(batches)}", flush=True)
        time.sleep(0.12)

    proposals: dict[str, str] = {}
    for key, source in sources.items():
        if key.startswith(VISIBLE_PREFIXES):
            existing = manual.get(key, project.get(key, "")).strip()
            if existing and format_tokens(source) == format_tokens(existing):
                proposals[key] = existing
    generated_sources = set(cache) | set(MANUAL)
    for key, source in sources.items():
        if key.startswith(VISIBLE_PREFIXES) and source in generated_sources:
            generated = MANUAL.get(source, project.get(key, results.get(source, ""))).strip()
            if generated and format_tokens(source) == format_tokens(generated):
                proposals[key] = generated
    rejected = 0
    for key, source in targets.items():
        target = results.get(source, "").strip()
        if not target or format_tokens(source) != format_tokens(target):
            rejected += 1
            continue
        proposals[key] = target

    for key, source in sources.items():
        if key.startswith(VISIBLE_PREFIXES) and source in MANUAL:
            proposals[key] = MANUAL[source]

    proposal_path = report_dir / "Wakfu_Dunya_Etiketi_Ceviri_Onerileri_v44.json"
    save_json(proposal_path, proposals)
    cache_snapshot = dict(cache)
    for key, target in proposals.items():
        cache_snapshot[sources[key]] = target
    save_json(cache_path, cache_snapshot)
    if args.apply:
        for key, target in proposals.items():
            project[key] = target
            manual[key] = target
        save_json(project_path, project)
        save_json(manual_path, manual)
    print(json.dumps({
        "proposals": len(proposals), "rejected": rejected,
        "applied": bool(args.apply), "proposal_file": str(proposal_path),
    }, ensure_ascii=False), flush=True)
    return 0 if rejected == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
