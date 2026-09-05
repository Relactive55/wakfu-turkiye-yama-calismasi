#!/usr/bin/env python3
"""Apply the first independently reviewed v44 repair batch.

Only exact source strings, exact keys, and narrowly defined environment-quest
patterns are changed. Skill and item names referenced by those strings remain
in their original English form.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"
MANUAL = ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"
TERMINOLOGY = ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"
SOURCE_JAR = ROOT / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar"

NORMALIZE_ONE_LEADING_SPACE_KEYS = {
    "content.67.189", "content.67.228", "content.67.234",
}

# content.8 ailesi savaşta görünen durum/mekanik adlarıdır ve kullanıcı
# tercihiyle özgün İngilizce kalır. Bu yedi anahtar ise sınıf tanıtım kartındaki
# "Gameplay" arayüz sekmesidir; durum adı olmadığı için Türkçeleştirilir.
TRANSLATABLE_COMBAT_STATE_KEYS = {
    "content.8.1263", "content.8.2718", "content.8.4048",
    "content.8.4260", "content.8.5817", "content.8.5865",
    "content.8.7386",
}

# Teknik olarak content.15 havuzunda bulunurlar ancak ekranda eşya adı olarak
# değil, envanter/karakter arayüz etiketi olarak gösterilirler.
TRANSLATABLE_INVENTORY_UI_KEYS = {
    "content.15.2175",
    "content.15.24267",
    "content.15.27097", "content.15.27098", "content.15.27099",
    "content.15.27110", "content.15.29612",
}

EXTRA_PROTECTED_COMBAT_NAME_KEYS = {
    "content.6.1049",  # Will-o-the-Wisp
}

REFERENCE_VARIANT_REPLACEMENTS = {
    "Against the Clock": (("Zamana Karşı", "Against the Clock"),),
    "Rogue Master": (("Rogue Üstat", "Rogue Master"),),
    "Gravity Well": (("Yerçekimi Kuyusu", "Gravity Well"),),
    "Celestial Portal": (
        ("Göksel Portalı", "Celestial Portal'ı"),
        ("Göksel Portal", "Celestial Portal"),
    ),
    "Light My Fire": (("Ateşimi Yak", "Light My Fire"),),
    "Milking It": (("Sağım Vakti", "Milking It"),),
    "Six Roses": (("Altı Gül", "Six Roses"),),
    "Shot from the Edge": (("Kenardan Atış", "Shot from the Edge"),),
    "Health Steal": (("Can Çalma", "Health Steal"),),
    "Wakfu Well": (("Wakfu Kuyusu", "Wakfu Well"),),
    "Wounded Straps": (("Yaralı Kayışlarla", "Wounded Straps ile"),),
    "Abacus Compendium": (("Abacus Derlemesi", "Abacus Compendium"),),
    "Accelerated Growth": (("Hızlandırılmış Büyüme", "Accelerated Growth"),),
    "Ancestral Essence": (("Atalardan Kalma Öz", "Ancestral Essence"), ("Ancestral Öz", "Ancestral Essence")),
    "Ash Wood": (("Ash Odun", "Ash Wood"), ("Dişbudak odunu", "Ash Wood")),
    "Ancient Bell": (("Kadim Çan", "Ancient Bell"),),
    "Ancestral Souper-Glou": (("Atalardan Kalma Souper-Glou", "Ancestral Souper-Glou"),),
    "Basic Flour": (("Basic Un", "Basic Flour"),),
    "Basic Handle": (("Temel Sap", "Basic Handle"),),
    "Basic Souper-Glou": (("Temel Souper-Glou", "Basic Souper-Glou"),),
    "Bow of Pwodding": (("Pwodding'in Yayı", "Bow of Pwodding"),),
    "Broken Noxine": (("Kırık Noxine", "Broken Noxine"),),
    "Bwork Artifact": (("Bwork Eserini", "Bwork Artifact'ı"), ("Bwork Eseri", "Bwork Artifact")),
    "Celestial Flower": (("Göksel Çiçek", "Celestial Flower"),),
    "Chafer Essence": (("Chafer Özü", "Chafer Essence"), ("Chafer Öz", "Chafer Essence")),
    "Clot the Crapulous": (("Sefih Clot", "Clot the Crapulous"),),
    "Cloudy Key": (("Bulutlu Anahtar", "Cloudy Key"),),
    "Coarse Souper-Glou": (("Kaba Souper-Glou", "Coarse Souper-Glou"),),
    "Coat of the Sorcerer-King": (("Büyücü-Kral Paltosu", "Coat of the Sorcerer-King"),),
    "Contaminated Wheat": (("Contaminated Buğday", "Contaminated Wheat"),),
    "Cornpop Fragments": (("Cornpop Parçasını", "Cornpop Fragments'ı"), ("Cornpop Parçası", "Cornpop Fragments")),
    "Crozolily Bouquet": (("Crozolily Buketini", "Crozolily Bouquet'yi"), ("Crozolily Buketi", "Crozolily Bouquet")),
    "Crumpled Pages": (("Buruşuk Sayfaları", "Crumpled Pages'ı"),),
    "Dark Roots": (("karanlık kök", "Dark Roots"), ("Karanlık Kök", "Dark Roots")),
    "Details of the Agricultural Competition - Volume I": (("Tarım Yarışmasının Ayrıntıları - Cilt I", "Details of the Agricultural Competition - Volume I"),),
    "Details of the Agricultural Competition - Volume II": (("Tarım Yarışmasının Ayrıntıları - Cilt II", "Details of the Agricultural Competition - Volume II"),),
    "Details of the Agricultural Competition - Volume III": (("Tarım Yarışmasının Ayrıntıları - Cilt III", "Details of the Agricultural Competition - Volume III"),),
    "Details of the Agricultural Competition - Volume IV": (("Tarım Yarışmasının Ayrıntıları - Cilt IV", "Details of the Agricultural Competition - Volume IV"),),
    "Details of the Agricultural Competition - Volume V": (("Tarım Yarışmasının Ayrıntıları - Cilt V", "Details of the Agricultural Competition - Volume V"),),
    "Divine Souper-Glou": (("İlahi Souper-Glou", "Divine Souper-Glou"),),
    "Durable Souper-Glou": (("Dayanıklı Souper-Glou", "Durable Souper-Glou"),),
    "Eternal Snowflake Powder": (("Ebedî Kar Tanesi Tozu", "Eternal Snowflake Powder"),),
    "Eternal Souper-Glou": (("Ebedî Souper-Glou", "Eternal Souper-Glou"),),
    "Exquisite Souper-Glou": (("Nefis Souper-Glou", "Exquisite Souper-Glou"),),
    "False Note": (("yanlış not", "False Note"), ("Yanlış Not", "False Note")),
    "Father Kwismas Costume": (("Father Kwismas Kostümü", "Father Kwismas Costume"),),
    "Fragile Souper-Glou": (("Kırılgan Souper-Glou", "Fragile Souper-Glou"),),
    "Harry Boots Fragments": (("Harry Boots Parçasını", "Harry Boots Fragments'ı"), ("Harry Boots Parçası", "Harry Boots Fragments")),
    "Hazel Wood": (("Hazel Odun", "Hazel Wood"),),
    "Hunter's Instinct": (("Avcı's Instinct", "Hunter's Instinct"), ("Avcı İçgüdüsü", "Hunter's Instinct")),
    "Ice Knight Sword": (("Buz Şövalyesi Kılıcı", "Ice Knight Sword"),),
    "Ice Zing": (("Buz Zingi", "Ice Zing"),),
    "Imperfect Plank": (("Imperfect Tahta", "Imperfect Plank"),),
    "Imperfect Souper-Glou": (("Kusurlu Souper-Glou", "Imperfect Souper-Glou"),),
    "In Search of Immortality - Volume I": (("Ölümsüzlük Arayışı - Cilt I", "In Search of Immortality - Volume I"),),
    "In Search of Immortality - Volume II": (("Ölümsüzlük Arayışı - Cilt II", "In Search of Immortality - Volume II"),),
    "In Search of Immortality - Volume III": (("Ölümsüzlük Arayışı - Cilt III", "In Search of Immortality - Volume III"),),
    "Infernal Souper-Glou": (("Cehennemî Souper-Glou", "Infernal Souper-Glou"),),
    "Iron Ore": (("Iron Cevher", "Iron Ore"),),
    "Ivory Dofus": (("Fildişi Dofus", "Ivory Dofus"),),
    "Juicy Sap": (("Sulu Özsu", "Juicy Sap"), ("Juicy Özsu", "Juicy Sap")),
    "Karnivorous Kebab": (("Etçil Kebap", "Karnivorous Kebab"),),
    "Key of Death": (("Ölüm Anahtarı", "Key of Death"),),
    "Key of Immortality": (("Ölümsüzlük Anahtarı", "Key of Immortality"),),
    "Key of Life": (("Yaşam Anahtarı", "Key of Life"),),
    "Larval Powder": (("Larva Tozu", "Larval Powder"),),
    "Li'l Owain's Armor": (("Li'l Owain's Zırh", "Li'l Owain's Armor"),),
    "Lord of the Rats' Ceremonial Boots": (("Fareler Efendisi Tören Botu", "Lord of the Rats' Ceremonial Boots"),),
    "Magic Kwismas Tree Wood": (("Magic Kwismas Tree Odun", "Magic Kwismas Tree Wood"),),
    "Marmalot Wood": (("Marmalot Odun", "Marmalot Wood"),),
    "Meridia Insignia": (("Meridia Nişanı", "Meridia Insignia"),),
    "Mollusky Egg": (("Mollusky Yumurtasını", "Mollusky Egg'i"), ("Mollusky Yumurtası", "Mollusky Egg")),
    "Moowolf Bell": (("Moowolf Çanı", "Moowolf Bell"),),
    "Mortified Essence": (("Mortified Öz", "Mortified Essence"),),
    "Moskito Wings": (("Moskito Kanatlar", "Moskito Wings"),),
    "Mystical Leather": (("Mystical Deri", "Mystical Leather"),),
    "Mystical Souper-Glou": (("Mistik Souper-Glou", "Mystical Souper-Glou"),),
    "Osamodas Powder": (("Osamodas Tozu", "Osamodas Powder"),),
    "Precious Souper-Glou": (("Değerli Souper-Glou", "Precious Souper-Glou"),),
    "Primal Skin": (("Primal Deri", "Primal Skin"),),
    "Raw Souper-Glou": (("Ham Souper-Glou", "Raw Souper-Glou"),),
    "Refined Souper-Glou": (("Rafine Souper-Glou", "Refined Souper-Glou"),),
    "Royal Feather": (("Kraliyet Tüyünü", "Royal Feather'ı"), ("Kraliyet Tüyü", "Royal Feather")),
    "Royal Tofu Feather": (("Kral Tofu Tüyünü", "Royal Tofu Feather'ı"), ("Kral Tofu Feather", "Royal Tofu Feather"), ("Kral Tofu Tüyü", "Royal Tofu Feather")),
    "Rustic Souper-Glou": (("Rustik Souper-Glou", "Rustic Souper-Glou"),),
    "Schnek Egg": (("Schnek Yumurtasını", "Schnek Egg'i"), ("Schnek Yumurtası", "Schnek Egg")),
    "Sea Boss": (("Sea Baş Canavar", "Sea Boss"), ("Deniz Canavarı", "Sea Boss")),
    "Seal of Companionship": (("Yoldaşlık Mührünü", "Seal of Companionship'ı"), ("Yoldaşlık Mührü", "Seal of Companionship")),
    "Selachii Egg": (("Selachii Yumurtasını", "Selachii Egg'i"), ("Selachii Yumurtası", "Selachii Egg")),
    "Sleeping Potion": (("Uyku İksiri", "Sleeping Potion"),),
    "Solid Souper-Glou": (("Katı Souper-Glou", "Solid Souper-Glou"),),
    "Spherolithic Encyclopedia": (("Spherolithic Ansiklopedisi", "Spherolithic Encyclopedia"),),
    "Teleport of Scriptures": (("Kutsal Yazılar Işınlaması", "Teleport of Scriptures"),),
    "Tropikoko Bark": (("Tropikoko Kabuk", "Tropikoko Bark"),),
    "Unidentified Powder": (("Tanımlanamayan Toz", "Unidentified Powder"),),
    "Wakfu Harvester": (("Wakfu Toplayıcısını", "Wakfu Harvester'ı"), ("Wakfu Toplayıcısı", "Wakfu Harvester")),
    "Weapons Master's Seal": (("Silah Ustası's Seal", "Weapons Master's Seal"),),
    "Wheat Straw": (("Buğday Straw", "Wheat Straw"),),
    "Zomkin Juice": (("Zomkin Suyu", "Zomkin Juice"),),
    "Bold Punishment": (("Cesur Ceza", "Bold Punishment"),),
    "Wall of Bones": (("Kemik Duvarı", "Wall of Bones"),),
    "Roll Again": (("Yeniden At", "Roll Again"),),
    "Heart of Light": (
        ("Işık Kalbi'nin", "Heart of Light'ın"),
        ("Işık Kalbi'ni", "Heart of Light'ı"),
        ("Işık Kalbi", "Heart of Light"),
    ),
    "Twilight Beam": (("Alacakaranlık Işını", "Twilight Beam"),),
    "Ouginak's Fury": (("Ouginak'ın Öfkesi", "Ouginak's Fury"),),
    "Powder Wall": (
        ("Barut Duvarları", "Powder Wall'lar"),
        ("Barut Duvarı", "Powder Wall"),
    ),
    "Against Nature": (("Doğaya Karşı", "Against Nature"),),
    "Count Harebourg": (("Kont Harebourg", "Count Harebourg"),),
    "Divine Koko": (("İlahi Koko", "Divine Koko"),),
    "Koko Blow": (("Koko Darbesi", "Koko Blow"),),
    "Gobball War Chief": (
        ("Gobball Savaş Şefi'nden", "Gobball War Chief'ten"),
        ("Gobball Savaş Şefi'nin", "Gobball War Chief'in"),
        ("Gobball Savaş Şefi'ne", "Gobball War Chief'e"),
        ("Gobball Savaş Şefi'ni", "Gobball War Chief'i"),
        ("Gobball Savaş Şefi", "Gobball War Chief"),
    ),
    "Belt of the Winds": (
        ("Rüzgâr Kemeri'ni", "Belt of the Winds'i"),
        ("Rüzgâr Kemeri", "Belt of the Winds"),
        ("Rüzgarların Kuşağı", "Belt of the Winds"),
    ),
    "Snow Bow Meow": (("Kar Bow Meow", "Snow Bow Meow"),),
    "Bow Meow Fish": (("Bow Meow Balığı", "Bow Meow Fish"), ("Breaded Balık", "Breaded Fish")),
    "Will-o'-the-Wisp": (
        ("Gezgin Işığın", "Will-o'-the-Wisp'in"),
        ("Gezgin Işığı", "Will-o'-the-Wisp'i"),
        ("Gezgin Işık", "Will-o'-the-Wisp"),
    ),
    "Woyal Bow of Pwodding": (("Pwodding'in Woyal Yayı", "Woyal Bow of Pwodding"),),
    "Black Cawwot Juice": (
        ("Kara Cawwot Suyu'nu", "Black Cawwot Juice'u"),
        ("Kara Cawwot Suyu", "Black Cawwot Juice"),
    ),
    "Xelor's Sandglass": (
        ("Xelor'un Kum Saati'ni", "Xelor's Sandglass'ı"),
        ("Xelor'un Kum Saati", "Xelor's Sandglass"),
        ("Xelor'un Kumsaati", "Xelor's Sandglass"),
    ),
    "Gobbowl Ball": (
        ("Gobbowl Topunu", "Gobbowl Ball'u"),
        ("Gobbowl topunu", "Gobbowl Ball'u"),
        ("Gobbowl Topu", "Gobbowl Ball"),
        ("Gobbowl topu", "Gobbowl Ball"),
    ),
    "Gobbowlium Codex": (
        ("Gobbowlium Kodeksi'ni", "Gobbowlium Codex'i"),
        ("Gobbowlium Kodeksi", "Gobbowlium Codex"),
    ),
    "Royal Bauxite": (("Kraliyet Boksiti", "Royal Bauxite"),),
    "Moogrrtrool Boots": (
        ("Moogrrtrool Botlarıyla", "Moogrrtrool Boots'la"),
        ("Moogrrtrool Botları", "Moogrrtrool Boots"),
    ),
    "Trinket Box": (
        ("Ziynet Kutusu'nda", "Trinket Box'ta"),
        ("Ziynet Kutusu", "Trinket Box"),
        ("Ziynet Kutu", "Trinket Box"),
    ),
    "Breaded Fish": (("Ekmekli Balık", "Breaded Fish"), ("Breaded Balık", "Breaded Fish")),
    "Magic Cawwot Juice": (
        ("Sihirli Cawwot Suyu'nu", "Magic Cawwot Juice'u"),
        ("Sihirli Cawwot Suyu", "Magic Cawwot Juice"),
    ),
    "Lifen Sole Boots": (("Lifen Sole Botlarıyla", "Lifen Sole Boots'la"), ("Lifen Sole Botları", "Lifen Sole Boots")),
    "Golden Palm": (("Altın Palmiye", "Golden Palm"),),
    "Sleeping Powder": (("Uyku Tozunu", "Sleeping Powder'ı"), ("Uyku Tozu", "Sleeping Powder")),
    "Ethernal Essence": (("Ethernal Öz", "Ethernal Essence"),),
    "Bulia Powder": (("Bulia Tozunu", "Bulia Powder'ı"), ("Bulia Tozu", "Bulia Powder")),
    "Black Bow Meow": (("Kara Bow Meow", "Black Bow Meow"),),
    "Royal Wool": (("Kraliyet Yününü", "Royal Wool'u"), ("Kraliyet Yünü", "Royal Wool")),
    "Dazzling Belt": (("Dazzling Kemer", "Dazzling Belt"), ("Göz Kamaştırıcı Kemer", "Dazzling Belt")),
    "Innovative Boots": (("Innovative Botlar", "Innovative Boots"),),
    "Sacred Basalt": (("Kutsal Bazaltı", "Sacred Basalt'ı"), ("Kutsal Bazalt", "Sacred Basalt")),
    "Bygone Hand": (("Geçmişin Eli'ni", "Bygone Hand'i"), ("Geçmişin Eli", "Bygone Hand")),
    "Dial Hand": (("Kadran İbresi", "Dial Hand"),),
    "Panache Cloak": (("Panache Pelerin", "Panache Cloak"),),
    "Water Clock": (
        ("Su Saati'ni", "Water Clock'ı"),
        ("Su Saati'nin", "Water Clock'ın"),
        ("Su Saati", "Water Clock"),
    ),
    "Crocodyl Leather": (("Crocodyl Deri", "Crocodyl Leather"),),
    "Rampart Boots": (("Rampart Botlar", "Rampart Boots"),),
    "Mortifying Essence": (("Mortifying Öz", "Mortifying Essence"), ("Mortaklı Öz", "Mortifying Essence")),
    "Factory Worker Costume": (("Fabrika İşçisi Kostümü", "Factory Worker Costume"),),
    "Sandy Ore": (("Sandy Cevher", "Sandy Ore"),),
    "Rikiki Wand": (
        ("Rikiki Asası'nı", "Rikiki Wand'ı"),
        ("Rikiki Asası", "Rikiki Wand"),
    ),
    "Canoon Powder": (("Kanoon Barutu", "Canoon Powder"),),
    "Warmabones Belt": (("Warmabones Kemer", "Warmabones Belt"),),
    "Lemon Jelly Amulet": (("Lemon Jelly Tılsım", "Lemon Jelly Amulet"),),
}


KEY_EXACT = {
    # Karakteristik filtre kutularına sığan kısa alt/üst sınır etiketleri.
    "min": "En az",
    "max": "En çok",
    "rerollXp.info.notRight": (
        "İkincil karakterler için XP bonusu. Bu bonus, bir Güçlendirici ile "
        "x[#1.1]'ye yükseltilebilir."
    ),
    # Sınıf tanıtım kartındaki sekme başlığı.
    "content.8.1263": "Oynanış",
    "content.8.2718": "Oynanış",
    "content.8.4048": "Oynanış",
    "content.8.4260": "Oynanış",
    "content.8.5817": "Oynanış",
    "content.8.5865": "Oynanış",
    "content.8.7386": "Oynanış",
    # content.15 havuzundan çağrılan envanter/karakter arayüz etiketleri.
    "content.15.2175": "Cepler",
    "content.15.24267": "Deneyim",
    "content.15.27097": "Yakın Dövüş Ustalığı",
    "content.15.27098": "Menzil Ustalığı",
    "content.15.27099": "Berserk Ustalığı",
    "content.15.27110": "İyileştirme Ustalığı",
    "content.15.29612": "Ara",
    # v44 son bağlam denetimi: Gerçek yetenek/eşya başvuruları özgün adla
    # bırakılır; aynı yazılışa sahip yaratık, mekân ve eylemler çevrilir.
    "aguabrial.fight.player.infos": "Aguabrial Scales: [#2]",
    "content.67.395": (
        "Vuuuu! Vuuuuuu! Al Howin geldi! Bu özel gün için Piece of Pumpkwin kullanarak nefis ikramlar hazırla. "
        "En güzel önlüğünü tak ve pişirmeye başla!Evil Lollipop nasıl yapılır: Piece of Pumpkwin x2"
        "Kısık ateşte kaynamaya bırak!Al Howin's Treat nasıl yapılır:\\n\\nPiece of Pumpkwin x1\\n\\n"
        "Bucket o' Water x1\\nEvil Lollipop x1\\n\\nTam ateşte 20 saniye pişir, soğumaya bırak ve afiyetle ye!"
        "\\n\\nAERW (Emekli Kötü Cadılar Derneği)"
    ),
    "content.75.3310": (
        "Pekâlâ, isteğini dikkatle not edeceğim... Ama okulun kapılarını önüne gelen her budalaya açmadığımızı "
        "bilmelisin. Kaydını tamamlamak için seni ilk sınava sokacağım. Gerekli öğrenme becerilerine sahipsen "
        "oldukça basit... Okulun alt katına dağıttığımız üç nesneyi bulmalısın: bir Blue-toned Pearl, biraz "
        "Precious Powder ve özellikle acemiler için bıraktığımız bir not."
    ),
    "content.75.3387": (
        "Yine merhaba... Kaydolmak için gereken eşyaları hâlâ getirmedin mi? Okula gerçekten katılmak istediğinden "
        "emin misin?... Hatırlatayım: Okulun alt katına dağıttığımız üç nesneyi bulmalısın; bir Blue-toned Pearl, "
        "biraz Precious Powder ve özellikle acemiler için bıraktığımız bir not."
    ),
    "content.76.7837": "Kızartmam gereken başka Bow Meow Fish'ler var. Sonra görüşürüz!",
    "content.75.2371": (
        "Haw haw haw! Birçok kişi Bwork Beer tarifimi ister. Ama kimse bilmez. Ben geleneksel tarif kullanır."
        "\\nBen özel malzeme ekler. Ve sen... asla... bilemez...!"
    ),
    "content.75.2027": (
        "Hayır, hayır, hayır. Bir anlaşmanın koşulları yeniden görüşülmez. Bana 10 Stolen Cargo getir, ben de sana "
        "Climbing Gear'ı vereyim."
    ),
    "content.75.2074": (
        "Bu Pure Taroudium'u getirdiğin için teşekkür ederim. Karşılığında Climbing Gear'ımı sana seve seve "
        "verirdim... ama korkunç bir şey oldu!"
    ),
    "content.13.97659": "korunur (Close Pwotection)",
    "no.incantation.for.agony.201": "**Bu kapıyı açmak için Divine Feca Incantation'a ihtiyacım var.",
    "content.63.5555": (
        "Misty Isle patronlarının hayaletlerini yendiğinden beri Ebony Dofus'un görkemini yeniden kazandığını "
        "hissediyorsun. Onu bütünüyle eski hâline döndürmek için şimdi Nox'u bir kez daha yenmelisin!"
    ),
    "content.75.7107": (
        "Misty Isle'da bulunan bütün Wakfu olağandışı. Yeterli miktarda Stasis ile denge kurarak Ebony Dofus'u "
        "yeniden dengeleyebilmelisin."
    ),
    "content.75.7109": (
        "Ebony Dofus sayesinde adada savaştığın en zorlu düşmanlar geri döndü. Son derece gerçekçi görünseler de "
        "bunlar sıradan hayaletler. Onlarla belirli bir Stasis seviyesinde savaşmayı unutma...\\n\\n*Bu yan görevi "
        "hazırlamak için harcanan çabayı içinden takdir edersin; görev, Misty Isle zindanlarını Stasis 3'te yeniden "
        "tamamlamanı gerekçelendirmek için elinden geleni yapıyor*"
    ),
    "content.63.1728": (
        "Eternal Firecracker üretmek için gereken tüm malzemelere sahipsin. Donalangelo'ya geri dön; böylece onu "
        "yapabilsin."
    ),
    "content.75.2525": (
        "Tek kelime daha etme! Yine o lanet Occult Cult, değil mi? Bir de anlamadığı ayinlere burnunu sokan o aptal "
        "Büyük Üstat! Ayinin çağırdığı varlığı geri püskürtmek için özel bir silaha ihtiyacın olacak. Bana biraz "
        "Larval Powder ve bir Hollow Tube getir. Gereken aracı hazırlayacağım."
    ),
    "content.67.393": (
        "Hank Skivin'in Stuffed Dragoturkey Recipe'ı:\"Stuffed Dragoturkey'in neden bu kadar lezzetli olduğunu biliyor "
        "musun? Malzemeleri bulmak için ter ve kan döktüğün için...\"Hazırlamak için şunları al:- 4 Chastenuts- 2 "
        "Lauwel Leaves- 2 Shallots - Ve bolca Hunk of Dragoturkey (elbette)Her şeyi içine doldur (sevgiyle; sevgiyi "
        "asla unutma) ve 20 saniye pişir.\\n\\nSon olarak afiyetle ye!\\n\\nMai-Tei Teisti"
    ),
    "content.67.394": (
        "Skank Hivin'in Stuffed Dragoturkey Recipe'ı:\"Stuffed Dragoturkey'in neden bu kadar lezzetli olduğunu "
        "biliyor musun? Malzemeleri bulmak için ter ve kan döktüğün için...\"Hazırlamak için şunları al:- 5 "
        "Chastenuts- 1 Lauwel Leaves- 4 Shallots \\n\\n- Ve bolca Hunk of Dragoturkey (elbette)\\n\\nHer şeyi içine "
        "doldur (sevgiyle; sevgiyi asla unutma) ve 20 saniye pişir.\\nSon olarak afiyetle ye!\\nMai-Tei Teisti"
    ),
    "incarnam.tuto.ui.spell.active.14.infos": (
        "Element büyülerine ek olarak bazı nötr büyülerin de var. İlki, Masqueraider'ın bir ikizini çağıran Masked "
        "Spirit'tir. Masked Spirit saldırabilir veya iyileştirebilir; ancak aldığı tüm hasar Masqueraider'a da aktarılır."
    ),
    "content.65.283": (
        "Zaten bir Merchant Haven Gem'in var ama iki tane olması daha iyi! \\nTezgâh kurup eşyalarını "
        "satabileceğini hatırlatmama gerek yok, değil mi? Tıss..."
    ),
    "shop.purchaseWebRedirection": (
        "Mystery Box'ını açmak için wakfu.com üzerindeki \"Topluluk\" bölümüne, ardından \"Hediye Kodu\" sayfasına git."
    ),
    "content.24.-1684": (
        "Ogrest's Tears'ın yol açtığı son kriz, yıllardır kuma gömülü hazineleri yavaş yavaş açığa çıkaran olağan "
        "dışı bir gelgit oluşturdu. En iyi ödülü almak için mümkün olduğunca çoğuyla etkileşime geç."
    ),
    "content.75.4024": (
        "Bu çok tuhaf. Ogrest's Wrath'ın Zinit Dağı'nda nasıl yoğunlaştığı üzerine yaptığım onca büyüleyici "
        "deneyden sonra... Onun senin içinde doğal biçimde yaşayarak yeteneklerini güçlendirebileceğini ummuştum, "
        "ama belli ki yanılmışım. Şimdi yapabileceğin en iyi şey eski dostum Moze'yi görmek. Sadida Krallığı'nda bir "
        "yerlerde. Tam olarak nerede bilmiyorum, ama alışılmadık tarzıyla onu bulmak zor olmamalı. Seni benim "
        "gönderdiğimi söyle."
    ),
    "content.75.4079": (
        "Thork Amulet'i, Great Wild Gobball Ring'i ve son derece nadir Padded Epaulettes'i "
        "arıyorum! Burada gerçek eşyalardan söz ediyorum; adını duyurmaya çalışan bir zanaatkârın yaptığı "
        "\"geliştirilmiş\" kopyalardan değil, saf ve el değmemiş olanlardan. Canavarların gerçekten taktığı sürümleri "
        "istiyorum."
    ),
    "content.63.2455": (
        "Pandora's Box, değiştirilmiş bir Krosmogolem tarafından korunuyor ve seni geçirmeye niyetli görünmüyor. "
        "Seninle İlahi Güç arasındaki son engel bu; onu yok etmenin bir yolunu bulmaktan başka çaren yok."
    ),
    "content.67.62": (
        "<b align=\"center\">Safely Salvaging Furniture</b>\\n\\n####\\n\\nÖncelikle bir <b>Tamirci</b> olarak "
        "<b>üretim mesleği</b> yapacaksın. Hiçbir şey hasat edemezsin ve ayrıca bir <b>İzne</b> ihtiyacın olacak."
        "\\n\\nBir <b>Tamirci</b>, Haven Bag'ler için <b>mobilya</b>, <b>döşeme</b> ve <b>üretim tezgâhları</b> "
        "yapar.\\n\\nBu yüzden <b>destekler</b> yapmak üzere <b>odun</b> almak için <b>Oduncuları</b>; bazı "
        "tariflerde ise <b>tahta</b> için yine aynı <b>Oduncuları</b> ziyaret etmen gerekir."
    ),
    "content.67.600": (
        "\\n<u>Belt of the Winds</u>:\\n1 x Emerald\\n1 x Crystal\\n2 x Dragon Pig Leather\\n1 x Piglet Leather"
        "\\n3 x Crocodyl Chief Scale\\n1 x Luthuthu Belt\\n2 x Purple Bwork Leather\\n\\n<u>Jellibelt:</u>"
        "\\n15 x Strawberry Jelly\\n20 x Mint Jelly\\n15 x Bluish Jelly\\n10 x Redjely\\n 5 x Blujely\\n1 x Lemon Jelly"
    ),
    "content.67.188": (
        " \\n<text align=\"center\"><b>The Ultra-Powerful</b></text>\\n[#icon 94:center]\\nThe Ultra-Powerful, "
        "Sadida'nın ana Bebeğidir. Diğer bütün Bebekleri çağırmak için kullanılır ve kendine ait alan etkili bir "
        "saldırısı vardır.\\n\\n<text align=\"center\"><b>The Voodoll</b></text>\\n[#icon 88:center]\\nThe Voodoll "
        "bir düşmana bağlanır. Bebeğe yapılan bütün tek hedefli saldırılar bağlı hedefe yönlendirilir."
    ),
    "content.63.3589": (
        "Unique Ring bulundu ve Alfredon artık aramızda değil. Yine de görevi son derece önemli. Unique Ring'i "
        "Or'Hodruin Yanardağı'nın kalbinde yok edecek başka bir gönüllüye ihtiyacımız var. Bu iş tamamlanmadan önce "
        "muhtemelen Alevlerin Efendisi Sor'Hon'un yenilmesi gerekecek."
    ),
    "content.63.1646": (
        "Bulduğun Bwork Madencisi, arkaosologlar hakkında daha fazla bilgi edinmek için Bwork Şefi'yle görüşmeni "
        "önerdi. Ancak saygıdeğer liderlerinin seni muhatap almasını istiyorsan onun koku ölçütlerine uyman gerekecek. "
        "Bir kucak Worn Wild Gobball Wool, Bwork kokusunu andıran bir \"parfüm\" hazırlamak için doğru başlangıç olacaktır."
    ),
    "content.75.2333": (
        "Yine Bwork olmayanlar. Bwork olmayanlar iyi değil. Eski kadim Bwork Tapınağı'na gider. Kaz kaz kaz, toz "
        "toprak.\\nAma sen Tapınağa gidemez. Tapınak Bwork Kampı'nda. Bwork Şefi, Bwork olmayanı sevmez. Git, şefe "
        "Bworkların dostu olduğunu göster. Sen Bwork gibi de kokmaz. On Worn Wild Gobball Wool sana güzel pis koku "
        "verir; olması gerektiği gibi."
    ),
    "content.63.1721": (
        "Görünüşe göre Shreddie, yalnızca Astrub Şövalyesi adıyla bilinen gizemli bir Astrublu paralı askeri esir "
        "aldı.\\nOgrest Tarikatı'ndaki kötülerin değersiz bir adağına dönüşmeden önce gidip onu hemen kurtarmalısın!"
    ),
    "content.63.1726": (
        "Görünüşe göre Shreddie, yalnızca Astrub Şövalyesi adıyla bilinen gizemli bir Astrublu paralı askeri esir "
        "aldı.\\nOgrest Tarikatı'ndaki kötülerin değersiz bir adağına dönüşmeden önce gidip onu hemen kurtarmalısın!"
        "\\nShreddie, Astrub kanalizasyonunun nemli ve kasvetli bir köşesinde saklanıyor."
    ),
    "content.64.10830": "Büyük Mutfak Ustası Zomkin'i yen (uygun seviyede ve Stasis &gt;= 3 iken)",
    "content.64.11392": (
        "Büyük Mutfak Ustası Zomkin'i yen (uygun seviyede, Stasis &gt;= 3 ve 1 dikilitaş etkinken)"
    ),
    "content.64.2919": "Tekrarlanabilir görevi tamamla: Büyük Mutfak Ustası Zomkin ile Patron Avı",
    "content.64.5817": "Büyük Mutfak Ustası Zomkin'i öldür",
    "content.64.8688": "Büyük Zomkin'in Kompostu Zindanı'nda Büyük Mutfak Ustası Zomkin'i yen",
    "LIFE_STOLEN_BONUS": "Sağlık Çalma bonusu",
    "moon.collector.croco.start": (
        "Otomai'nin Müritleri memnun ve Crocodyl Dandy artık platformunda serbest!\\n\\nZindan dikilitaşlarında "
        "kullanılabilen özel eşya ve kaynakları toplamak için bu fırsattan yararlan."
    ),
    "content.63.5272": "Gündüz vakti Çirkinler Kulesi'nin patronlarını yen.",
    "content.64.10586": "Çirkinler Kulesi'ni tamamla (uygun seviyede ve Stasis &gt;= 3 iken)",
    "content.64.10587": "Çirkinler Kulesi'ni tamamla (uygun seviyede ve Stasis &gt;= 4 iken)",
    "content.64.10588": "Çirkinler Kulesi'ni tamamla (uygun seviyede ve Stasis &gt;= 5 iken)",
    "content.64.10589": "Çirkinler Kulesi Zindanı'nı tamamla",
    "content.64.10592": "Başarımı tamamla: Çirkinler Kulesi I",
    "content.64.10593": "Başarımı tamamla: Çirkinler Kulesi II",
    "content.64.10594": "Başarımı tamamla: Çirkinler Kulesi III",
    "content.64.369": "Çirkinler Kulesi'ni ziyaret et",
    "content.64.4663": "Çirkinler Kulesi'ne git ve Lela'yı yen",
    "content.64.6522": "Çirkinler Kulesi Zindanı'nı tamamla",
    "content.64.6658": (
        "Çirkinler Kulesi Zindanı'nda Lela'yı veya Hill Hazize Zindanı'nda Kral Crackler'ı yen"
    ),
    "content.64.7102": "Çirkinler Kulesi Zindanı'nı uygun seviyede ve Stasis &gt;= 3 iken tamamla",
    "content.64.7103": "Çirkinler Kulesi Zindanı'nı uygun seviyede ve Stasis &gt;= 4 iken tamamla",
    "content.64.7104": "Çirkinler Kulesi Zindanı'nı uygun seviyede ve Stasis &gt;= 5 iken tamamla",
    "content.64.8561": "Çirkinler Kulesi Zindanı'nı 50. seviyede tamamla",
    "content.64.8639": "Çirkinler Kulesi Zindanı'nda Lela'yı yen",
    "protector.specialevent.17": (
        "Şu sesi duyuyor musun? Bu, Sweeny Toad'ın aşk şarkısı. Çirkinler Kulesi civarında bir tane olmalı."
    ),
    "quest.amakna.missmoches.03.30": (
        "Aslında ben Lela'yım! Burası Çirkinler Kulesi; senin gibi maceracıları kendi amaçlarımız için yakalarız. "
        "Ne amaçla olduğunu söylemeyeceğim."
    ),
    "content.86.122": "Silah Demirhanesinin Yeniden İnşası",
    "content.86.123": "Silah Demirhanesinin Yeniden İnşası",
    "content.86.124": "Silah Demirhanesinin Yeniden İnşası",
    "content.86.121": "Ahşap Tornanın Yeniden İnşası",
    # Dünya haritasında özel ad korunurken açıklayıcı bölüm Türkçeleştirilir.
    "content.77.31": "Larvicyd, Yanlış Türden Huzur",
    "content.77.85": "Gobball Zindanı",
    "content.77.99": "Incarnam - Ruhlar Geçidi",
    "content.77.101": "Incarnam - Crozolily Çayırı",
    "content.77.141": "Incarnam - Xytler",
    "content.77.290": "Kara Mırıltı",
    "content.77.315": "Kelba Yedeği",
    "content.77.446": "Crackapult Poligonu",
    "content.77.447": "Kaya",
    "content.77.453": "Fısıltı Hisarı",
    "content.77.461": "Macawker'ın Zulası",
    "content.77.554": "Jellix Gösterisi",
    "content.77.585": "Terk Edilmiş Cawwot Deposu",
    "content.77.588": "Lenald Hapishanesi",
    "content.77.592": "Geçici Taht Odası",
    "content.77.593": "Yasak Laboratuvar",
    "content.77.1231": "Açık Deniz Adası",
    "content.77.1249": "Neşeli Riktus",
    "content.77.1299": "Shhhudo Hapishanesi",
    "content.77.1450": "Neo Pastörizatör",
    "content.77.1453": "Neo Wa'nın Kalesi",
    "content.77.733": "Nokta",
    "content.77.1121": "Gemi",
    "aptitude.restat.one.page.popup": (
        "Bu Özellikler sayfasını sıfırlamak için bir \"Characteristics Reset\" kullanın."
    ),
    "content.63.3615": (
        "Darkli Moon'dan \"Darkli Moon Hammer\"ı aldıktan sonra Zinit'teki Üst Yamaç'ta Kali ile konuş."
    ),
    "content.75.2010": (
        "*bellek başlatılıyor* *bilgiler derleniyor* Harebourg Kontluğu'nun avlusu, Harebourg Şatosu'nun kalbi - "
        "Count Harebourg'un malikânesi - levazım subayı Sylargh - son zamanlarda görülmedi..."
    ),
    "content.16.29185": "Hareket hâlindeki son derece etkili Condemner için ideal bir aksesuar.",
    "content.38.1131": "Nekrodünya",
    "content.54.924": "Don Dünyası",
    "content.54.929": "Don Dünyası",
    "content.61.419": "Don Dünyası",
    "content.61.598": "Don Dünyası",
    "content.77.325": "Don Dünyası",
    "content.89.666": "Don Dünyası",
    "content.137.48": "Don Dünyası",
    "content.54.2157": "Nekrodünya",
    "content.54.2245": "Nekrodünya",
    "content.61.890": "Nekrodünya",
    "content.61.891": "Nekrodünya",
    "content.61.892": "Nekrodünya",
    "content.77.1403": "Nekrodünya",
    "content.77.1405": "Nekrodünya",
    "content.89.4366": "Nekrodünya",
    "content.137.196": "Nekrodünya",
    "quest.dd.ch1.cinematique.eminence.lieu": "Srambad'da Bir Yer...",
    "content.35.7623": "Bonta Maddesiz Üniversitesi",
    "content.62.2608": "İmdat!",
    "content.16.26736": "Kullanımdan Kaldırılmış Eşya",
    "content.85.255": "Kapı",
    "content.121.205": "Kralın Emirleri",
    "content.121.212": "Puddly Dağları",
    "content.121.213": "Shhhudoku Krallığı",
    "content.121.227": "Cap'n Amakna'nın Haritası",
    "content.121.228": "Cap'n Flex'in Haritası",
    "content.121.230": "Captain Hake'in Haritası",
    "content.121.231": "Cap'n Haba'nın Haritası",
    "content.121.232": "Cap'n Nebo'nun Haritası",
    "content.121.235": "Cap'n Krik'in Haritası",
    "content.121.238": "Cap'n Craps'in Haritası",
    "content.121.239": "Cap'n Chafer'ın Haritası",
    "content.121.250": "Tyr Anis'in Seyir Defteri",
    "content.121.283": "Mezar",
    "content.121.284": "Mezar",
    "content.121.285": "Mezar",
    "content.121.286": "Mezar",
    "content.121.287": "Mezar",
    "content.121.327": "Eski Arşiv Parşömeni",
    "content.121.362": "Raval'ın Raporu",
    "content.121.364": "Raval'ın Araştırması",
    "content.121.407": "Dikilitaş",
    "content.121.209": "Fısıltılar",
    "content.155.26": "Meydan Okumalar",
    "content.155.185": "Saat Ustaları",
    "content.155.187": "Kızıl Mevsim",
    "content.155.158": "Crocodyl Tapınağı",
    "content.155.169": "Küp",
    "content.155.171": "Neo Karargâhı",
    "content.155.172": "Neo Karargâhı",
    "content.155.177": "Neo Teğmen",
    "content.155.178": "Neo Keşiş",
    "content.155.156": "Mabetler",
    "content.155.175": "İntikamcı Ruh",
    "desc.mru.barricader": "Barikat",
    "desc.mru.comportement.dopeul.roublard": "Rogue Dansı",
    "desc.mru.comportement.dopeul.slevtar": "Liesin Dansı",
    "desc.mru.comportement.dopeul.travlota": "Travalta Dansı",
    "desc.mru.orchestrion.playlist": "Kıyım Listesi",
    "desc.mru.phorreur.01": "Genç Drheller",
    "desc.mru.phorreur.02": "Olgunlaşmamış Drheller",
    "desc.mru.phorreur.03": "Yetişkin Drheller",
    "desc.mru.phorreur.04": "Olgun Drheller",
    "desc.mru.ranch.monster.action.brush": "Fırçala",
    "content.62.5315": "Rogue Dansı",
    # Oyuncuya görünen meslek/üretim istasyonu adları. Aynı kaynak metinler
    # content.15 altında eşya adı olarak geçerse aşağıdaki koruma aşaması onları
    # yine özgün İngilizceye döndürür.
    "content.59.87": "Ekmek Fırını",
    "content.59.103": "Ekmek Fırını",
    "content.59.151": "Taş Yerleştirme Tezgâhı",
    "content.59.152": "Ekmek Fırını",
    "content.59.154": "Ahşap Torna Tezgâhı",
    "content.59.166": "Küçük Cephanelik",
    "content.59.167": "Küçük Taş Yerleştirme Tezgâhı",
    "content.59.168": "Küçük Ekmek Fırını",
    "content.59.169": "Küçük Ocak",
    "content.59.170": "Küçük Ahşap Torna Tezgâhı",
    "content.59.176": "Küçük Kereste Tezgâhı",
    "content.59.177": "Küçük Damıtma Tezgâhı",
    "content.59.178": "Küçük Parlatma Tezgâhı",
    "content.59.179": "Küçük Değirmen Taşı",
    "content.59.95": "Büyük Yakın Dövüş Silahları Demirhanesi",
    "content.59.96": "Büyük Alan Etkili Silahlar Demirhanesi",
    "content.59.97": "Büyük Menzilli Silahlar Demirhanesi",
    "content.59.171": "Küçük Yakın Dövüş Silahları Demirhanesi",
    "content.59.172": "Küçük Menzilli Silahlar Demirhanesi",
    "content.59.173": "Küçük Alan Etkili Silahlar Demirhanesi",
    "content.35.8187": "Sınıf Sunağı",
    "content.35.7533": "Dor'Mor Mağarası",
    "content.35.7536": "Dor'Mor Mağarası",
    "tutorial.pm.title": "Hareket Puanları",
    "tutorial.fightChallenges.title": "Meydan Okumalar",
    "fight.foul.moon.tutorial.title": "Ay Ruhu",
    "tooltip.bylbyza.dimension.citron.Title": "Limon Boyutu",
    "tooltip.bylbyza.dimension.pomme.Title": "Nane Boyutu",
    "tooltip.Filacia.PopUp.Title": "Filacia'nın Bahçesi",
    "desc.mru.comportement.dopeul.requinou": "Sharkie Dansı",
    "quest.astrub.larve.rules.title01": "Larva Bakıcısı",
    "quest.DD.failletempo.rules.title": "Zaman Yarığı",
    "quest.frigost.nileza.armor.off.title": "TEHLİKE",
    "quest.frigost.nileza.grave.title": "TEHLİKE",
    "quest.huppermage.serre.tutorial.title": "Bir Tohum Nasıl Şalgama Dönüşür?",
    "quest.nations.ch05.cine.nemotilus.banquet.22": "Yorgunum...",
    "quest.osamosa.04.07": "HARİKA.",
    "quest.osamosa.04.13": "ELVEDA.",
    "quest.rewards.collected": "TOPLANDI",
    "chat.pipeName.personnal": "Kişisel [#1]",
    "desc.mru.chatouiller": "Gıdıkla",
    "content.13.173278": "Beraberlik",
    "resist.bonus": "Direnç Bonusu",
    "XELOR_RESOURCE": "Geçerli Saat",
    "content.66.65201": "Ulus Belediyesi",
    "content.88.994": "Mola Yeri",
    "worldDescription.arms_way": "Silah Yolu",
    "worldDescription.pabong_field": "Pabong Tarlası",
    "worldDescription.turfo_canyon": "Turfo Kanyonu",
    "content.13.380056": "Elemental Protection bozuldu.",
    "content.26.-1027": "Rekabetçi: Plack Plack Plock...",
    "content.26.-1932": "İşbirlikçi: Pandala Ghost Sürüleri",
    "content.47.15454": "Ne...!? Sen de kimsin? Çok mu erken? Beni çok erken uyandırdın! Bu izinsiz giriş de ne demek? Adalet yerini bulacak... hem de kesinlikle!!!",
    "content.47.16297": "Ne...!? Sen de kimsin? Çok erken! Beni çok erken uyandırdın! Bu izinsiz giriş de ne demek? Adalet yerini bulacak... hem de kesinlikle!!!",
    "content.47.16863": "Bir kez daha... mürekkep karası uçuruma... batmama izin ver...",
    "desc.mru.poseraffiche": "Bir afiş as",
    "quest.amakna.missmoches.04.08": "Sana söyleneni yap, Ydalipe; hayatımız buna bağlı.",
    "rushu.fight.start.dialog.02": "DAYAK YEMEYE GELİYORSUN...",
    "content.156.473": "<u><text align=\"center\">WAKFU Beta 1.91'e Hoş Geldin</u>!</text>\\nGüncelleme 1.91'in bu sürümünde yeni arayüzleri test edebilirsin: <text color=\"importantTextColor\">Makine,</text> <text color=\"importantTextColor\">Zindanlar</text> ve <text color=\"importantTextColor\">Ulaşım.</text> <text color=\"importantTextColor\">Sram yenilemesi</text> ile çeşitli oyun içi yaşam kalitesi iyileştirmeleri de test edilebilir.",
    "content.33.197708": "|2d[#4]/100|% verilen hasar, her <b>Fury</b> puanı için uygulanır\\n<b>Fury</b>, Sacrier'ın eksik Can Puanının 1.25 katına eşittir",
    "content.4.4606": "Sram'ın yüksek maliyetli büyüleri daha fazla hasar verir ancak artık Weak Point oluşturmaz. Execution ve Trauma büyüleri artık bu pasifin etkilerinden etkilenmez.",
    "content.4.7942": "Bu tarot kartı hedefe bonus verirken Ecaflip'e ceza uygular. Ecaflip, farkı kazanmak için kendisini ya da bonusu vermek için bir müttefikini hedefleyebilir.",
    "content.63.1750": "Ahabar Bar'Habi, Castuc'ların artan düşmanlığının nedenini belirlemek ve su kaynaklarına erişmek istiyor. Planına onay verdi, ancak Spiny Spine ve kampın çevresindeki kıt kaynaklar kostümü yapmak için yeterli olmayacak. Kılık değiştirmek için biraz Juicy Sap topla.",
    "content.63.2771": "İki oldu! Avuçlarında iki ılık ve gizemli Orichalcum var.\\nBir tane daha bulduğunda Sufokia'nın Batık Tapınağı'nın kapısını sonunda açabileceksin. İçinde hangi sırlar var, kim bilir...\\nO mutlu günü beklerken Eminerell Lebbocq da anlaşmanın kendine düşen kısmını yerine getirip yanlışlıkla sattığını iddia ettiği üçüncü ve son Orichalcum'un izini sürmeli...",
    "content.64.9715": "Rabet ile tekrar konuş",
    "content.75.4849": "*Pandora'nın yüzüne bakarsın. Arkadaşın soğuk bir kararlılıkla dolu görünür. Astrub'da kalan Pandora'ya pek benzemez. Geleceğin Pandora'sı On İkiler Dünyası'nı kurtarmak için ne gerekiyorsa yapmaya kararlı görünür.*",
    "content.76.13648": "*Büyü kaybolur. Bu tuhaf paylaşım anının, Sindrya duygularını paylaşma ihtiyacı duyduğu ancak bunu nasıl yapacağını bilmediği için yaşandığını anlarsın. Onun mahcupluğunu, başkalarıyla arasına koyduğu mesafeyi ve en önemlisi kederinin ağırlığını kavrarsın. Onu rahatsız etmemek için hiçbir şey söylememeye karar verirsin.*\\n\\n*Sindrya'ya veda edip Tal Kasha'nın piramidine doğru yola çıkarsın. Ouginak karşılık olarak nefes verir ve yumruklarını sıkar. \"Çölde Mahsur Kalan\" kişi ufka doğru gidişini izler; siluetin güneşin boğucu sıcağında hızla kaybolur.*",
    "bestRankName": "Lonca Lideri",
    "guild.rank.0": "Lonca Lideri",
    "autorun.mode.0": "Koş",
    "content.34.542": "Bir Avuç Kama",
    "content.34.584": "Şapkalar Çıkarılsın",
    "content.34.348": "Şans Ustası",
    "desc.mru.read": "Oku",
    "enchantment.apply.with.item.consumption": "Eşyayı feda et",
    "desc.mru.ddch4.sauver.pandora": "Pandora'yı kurtar",
    "tutorial.duel.title": "Düello Başlat",
    "desc.mru.attendre": "Bekle",
    "desc.wakfuGauge": "Wakfu / Stasis Ölçer",
    "character.sheet.masteriesAndResistances": "Ustalık ve Direnç",
    "content.13.339532": "[#1] {[=1]?hücre çekilir:hücre çekilir}",
    "content.138.15": "% Yapılan İyileştirme",
    "content.138.23": "Guild Standard İfadesi",
    "content.10.560": "Hedef, kullananın Hava Hasarı bonusundan yararlanır",
    "content.13.236810": "Granit Zırh çatlar",
    "content.13.237853": "Kaya Zırhı çatlar",
    "content.13.237913": "Kaya Zırhı çatlar",
    "content.13.238037": "Granit Zırh çatlar",
    "content.13.271375": "Kaya Zırhı çatlar",
    "content.16.20807": "Bu tomar, \"Ama Yap\" ifadesini öğretir.",
    "content.16.27348": "Pandalucia usulü kırsal bir et ezmesi; kornişon ve babbage ile servis edildiğinde en lezzetli hâline ulaşır.",
    "content.26.-2010": "Şhhudoku Meydan Okuması - Scramshells",
    "content.26.-2011": "Şhhudoku Meydan Okuması - Plantiguards",
    "content.26.-2012": "Şhhudoku Meydan Okuması - Pingwins",
    "content.33.153900": "Taşıyıcı art arda 2 tur boyunca hareket etmez ve büyü kullanmazsa:\\n[pl]En uzaktaki oyuncunun yakınına ışınlanır\\n[pl]Tüm çağrılmış yaratıkları yok eder\\n[pl]Tüm etki alanlarını yok eder\\nArt arda 3 tur sonra:\\n[pl]Taşıyıcı dokunulmaz olur\\n[pl]Müttefikleri Hasar ve Direnç kazanır\\n\\nCanavar yeniden normal biçimde oynadığı anda etkiler ortadan kalkar.",
    "content.33.155183": "10 AP/MP/WP Focus kaynaklı hasar aldıktan sonra dokunulmaz olur",
    "content.33.158306": "Enutrof'un altında 1 [$1$1ea]\\n[$1$6#1] [$1$6$1$1ea] [$1$6$1ae]\\n[$1$2#1] [$1$2$1$1ea] [$1$2$1ae] ve [$1$4$1ae]\\n[$1$3#1] [$1$3$1$1ea] [$1$3$1ae] ve [$1$7$1ae]\\n[$1$5#1] [$1$5$1$1ea] [$1$5$1ae]",
    "content.33.241640": "Enutrof'un altında 1 [$1$1ea]\\n[$1$6#1] [$1$6$1$1ea] [$1$6$1ae]\\n[$1$2#1] [$1$2$1$1ea] [$1$2$1ae] ve [$1$4$1ae]\\n[$1$3#1] [$1$3$1$1ea] [$1$3$1ae] ve [$1$7$1ae]\\n[$1$5#1] [$1$5$1$1ea] [$1$5$1ae]",
    "content.64.5170": "\"Etnop'un Meydan Okuması\" görevini 3 kez tamamla",
    "content.64.5176": "\"Etnop'un Meydan Okuması\" görevini 7 kez tamamla",
    "content.64.5645": "Kabul Ayini görevini tamamla",
    "content.64.6021": "Kork ifadesini kullan",
    "content.64.6899": "Otomai'ye geri dön (Imperfect Kel'Dwa envanterinde olmalıdır)",
    "content.64.9359": "Rekabet: Yabani Tofu'ların Geçtiğini Gördüm",
    "content.65.312": "Güzel, yeni bir Gemligem! \\nHaha, daha da güçlü olacağız ve daha fazla insanı yok edebileceğiz! \\nYa da görünümümü değiştiririz; sanırım hangi mücevher olduğuna bağlı...",
    "content.67.366": "\\n\\n<text align=\"center\"><b>Snappers\\n<i>19. Flovor - 20. Martalo</i></b></text>\\n\\nYağmurların efendisi Gök Gürültüsü Ulgrude, içinden geldiği gibi davranan fevri bir gençtir.\\nBir şey istediğinde onu elde etmek için elinden geleni yapar. Öfkelendiğinde korkunç şeyler yapabilir.\\nÂşık olduğundaysa onu hiçbir şey durduramaz: Güzeller güzeli Jiva'ya talip olmuş, onu baştan çıkarmaya kaç kez çalıştığının hesabını çoktan yitirmiştir!",
    "content.67.855": " \\n \\n\\n<text align=\"center\">NYL\\nARENASI\\nSEYİR DEFTERİ </text>\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\nKaptan Crook tarafından tutulmuştur (gemide hayatta kalan tek kişi Jacky Lilye Tstrong tarafından devralınmıştır)",
    "content.67.860": "\\nKAYIT 21\\n\\nAylarca \"gizli\" taşımacılık işlerini resmî sevkiyatların ardına sakladıktan sonra, sonunda kumarhane işine, daha doğrusu kumar işine nasıl geri döneceğimi buldum.\\nSon mal sevkiyatı sözleşmesinin bedeli, müşteri Brakmar Smissleriyle yaşadığı bir anlaşmazlığın ardından \"ortadan kaybolduğu\" için ödenemedi.\\nBu yüzden elimde bir sevkiyat dolusu schanker kaldı.\\nPlanım şu: Bir arena dövüşü turnuvası düzenleyeceğim. İnsan canavara karşı! Böylece özellikle Brakmar'da müşteri çekebileceğimden eminim. Sokaklarda dolaşan gözü kara Iop'lar, kendini beğenmiş Sacrier'lar ve açgözlü Enutrof'lar sayesinde aday sıkıntısı da çekmem.\\nKesemdeki kamaların şıngırtısını şimdiden duyabiliyorum...",
    "content.75.2032": "Tam olarak değil... Shustuft Crust'ın iblisi, Descendre ayının Koruyucusu, Brakmar'ın Müjdecisi ve Jiva'nın ezelî düşmanı Djaul bunu o zaman da böyle görmedi, şimdi de görmüyor. Gününün \"çalınmasına\" öfkelenen Djaul, mevsimlerin düzenini yeniden kurmak için geldi ve bununla da yetinmedi. İntikam olarak bütün adayı bitmek bilmeyen dondurucu bir kışa mahkûm etti.",
    "content.75.4274": "Hah! Senin gibi bir acemi savaş alanı hakkında hiçbir şey bilmez! Ben Nietvam Savaşı'nda da Revdun Muharebesi'nde de savaştım! Gazilerin gazisiyim... Üstelik karşıma çıkan{[1*]?:} ilk{[1*]?:} sıska bücürü{[1*]?:} işe almadım{[1*]?:}!",
    "content.75.4727": "Evet, ordu madencileri katletti. Madencileri gömmek için hepsi Neplopolis'e girince Charles-Henri onları dışarıdan kilitletti. Bütün kanıtlar ortadan kaldırılmalı, kimse konuşmamalıydı. Böylece ücretlerden tasarruf etti; yeni muhafızları olarak Bwork'leri ve makineleri tuttu.",
    "content.75.4931": "ÖNCE DALGANI OLUŞTURMALISIN.\\n\\nDALGA, OSAMOSA'NIN DÖRT BÖLGESİNDEN YARATIKLARIN BİR KARIŞIMINI İÇEREBİLİR.\\nSTASIS ZORLUĞU 1, 2, 3, 4 VEYA 5 OLARAK AYARLANABİLİR.\\n15, 25 VEYA 35 TUR SÜREBİLİR.\\n\\nDALGA BAŞLADIKTAN SONRA BU, SONSUZ BİR DÖVÜŞ OLUR. HER GRUBU YENDİĞİNDE YENİ CANAVARLAR ORTAYA ÇIKAR.",
    "content.75.5971": "*Hikâyeni anlatmak için otururken tünellerin nemli havasını ve rüzgârsızlığı hissedersin. Bu topraklara gelişini, Wabbit'lerle Lenald'lar arasındaki çatışmayı... ve Muvegitant'larla yaşananları anlatırsın.*\\n\\n*Patwick, anlattıkların karşısında şaşkınlığa kapılıp sözünü keser.*\\n\\nBir dakika... Bilinç sahibi Muvegitant'lawla kawşılaştığını mı söylüyowsun?",
    "content.75.5988": "*Patwick kararlılıkla sana bakar*\\n\\nOn İkilew Dünyası'nın geleceği...",
    "content.75.6450": "*Brakmarlı, adadaki Archaosologist yoldaşlarıyla buluşacağını söyler. Sonunda rahatlamış görünerek açık havaya çıkar. Sen ise Bworkana ve Zulnara'nın Bworkette klanıyla tuhaf bir ittifak kurdun. Klanın işlerine güçlü bir Shushu karışıyor; geçmişte yok edilen Crocodyl'larla ilgili, açığa çıkarılmayı bekleyen bir sır olduğunu seziyorsun.*\\n\\n*Şimdilik yorulmadan görevine geri dönersin.*",
    "content.76.10027": "Ne yapabileceğime bakacak, Renata ile Canar'a elimden geldiğince yardım edeceğim.\\n(Otomai'nin mektubunu teslim et)",
    "overhead.door.CHP": "Farle'ın Kayıp Yaban Toprakları'na Açılan Kapı",
    "server.description.0.false": "Bu, klasik WAKFU deneyimidir. Bir güçlendirici kullanarak ya da birden fazla hesaba giriş yaparak aynı anda birden fazla karakterle oynayabilirsin.",
    "server.description.3.false": "Neo Sunucular geçici etkinlik sunucularıdır. Bu sunucularda özel eşyalar ve bonuslar elde edebilirsin. Bir süre sonra Neo Sunucu, tarihî karşılığıyla birleşir. Bu gerçekleştiğinde karakter ilerlemesi, loncalar, eşyalar ve benzeri her şey klasik bir sunucuya aktarılır.\\n\\nBu, klasik WAKFU deneyimidir. Bir güçlendirici kullanarak ya da birden fazla hesaba giriş yaparak aynı anda birden fazla karakterle oynayabilirsin.",
    "stele.state.description.7211": "<b color=\"00E1A5\" align=\"center\">Dikilitaş 2: Eziyet Ordusu</b>\\n\\nBir canavar öldüğünde Tormentor onu 3 tur sonra diriltir.",
    "stele.state.description.7215": "<b color=\"71CF2B\" align=\"center\">Dikilitaş 2: Kazık Zinciri</b>\\n\\nPatron Kader Zinciri'nde değilse 200 Direnç ve %30 Verilen Hasar kazanır.",
    "tooltip.Gelificator.PopUp": "Jellificator parti yapmaya bayılır ama hızlı ol:\\n\\n- Her tur Jöleleşme seviyen artar. 50. seviyeye ulaştığında dövüşü kaybedersin.\\n\\n- Jellificator'ın aldığı her darbe Jely Damlası seviyesini 1 azaltır. Seviye 0'a ulaştığında Jellificator dövüşü kaybeder.",
    "tutorial.DD.srambad.vol.description.03": "- Her suç (Hırsızlık veya Yankesicilik), fark edilmen için yeni bir fırsattır\\n- Bir muhafızın ya da yoldan geçenin gözü önünde suç (Hırsızlık veya Yankesicilik) işlersen hemen fark edilirsin\\n- Fark edilirsen muhafızlar hem senin hem de müttefiklerinin peşine Bulldagger'ları salar\\n- Bir Bulldagger, fark edilmiş bir karakteri yakalarsa onu hemen dövüşten çıkarır ve Yankesicilik etkinliğine katılımını sona erdirir\\n- Bulldagger'lardan kaçmak için Kemik Yığınlarına saklan\\n\\nİpuçları: \\n\\n - Bir Bulldagger'ı yavaşlatmak için Poisoned Bone kullan\\n- Bir Kemik Yığınının yakınında kalarak yoldan geçenlerden çalmaya çalış",
    "content.63.3226": "Kelba'ya git ve Paws of Ecaflip eserini geri almak için \"Ecaflip Eseri Akıncıları - Yüz Yüze\" görevini tamamla.",
    "content.64.6194": "Otomai's Disciple'a 1 Morfor's Horn götür",
    "content.75.3905": "Bu eserler... Doğru anladıysam seninle gelmeme izin vermeyecekler. Görünüşe göre aynı anda yalnızca bir kişi kullanabiliyor. Bu da demek oluyor ki... HEPSİNİ BANA VER!!!",
    "content.76.12156": "Pandora öldü mü?",
    "content.77.838": "Atölye Evi \"Pandora'nın Mekânı\"",
    "content.8.2035": "Gely Damlası Uygulaması",
    "content.9.1475": "Hava Çemberi bu elementte hedefi korur veya zayıflatır.",
    "content.34.286": "Asse'nin Ası",
    "content.62.3070": "Oktapodas Sığınağı Finali",
    "content.62.3162": "Whirlcraft Savaşı: Final",
    "stele.state.description.8169": "<b color=\"892BCF\" align=\"center\">Dikilitaş 3: Yakın Destek</b>\\n\\nWa, tüm muhafızlarını kaybettikten sonra takviye çağırır.",
    "quest.brume.foret.00.35": "Bu 500'den az! Ne ezik ama; bu adamın bir yumurta bulduğuna inanamıyorum.",
    "stele.state.description.7216": "<b color=\"00E1A5\" align=\"center\">Dikilitaş 3: Yalnızlık</b>\\n\\nBir oyuncu turunu bir canavardan en az 9 hücre uzakta bitirdiğinde canavar 75 Element Direnci ve 1 MP kazanır (1 tur, birikebilir)",
    "content.10.979": "Element büyülerine [#1] seviye",
    "content.30.979": "Element büyülerine [#1] seviye",
    "content.4.6272": "Ouginak, verdiği dolaylı hasarın bir kısmını çalarak Zırha dönüştürür. Bu, zehir gibi kendi turu dışında verilen hasardır. Karşılığında verdiği hasar azalır. Canine Art ile kazanılan Zırh, tur başına Ouginak'ın azami Can Puanının %50'siyle sınırlıdır.",
    "content.4.6949": "Cra, element büyülerini doğal olarak 2 hücre daha uzağa kullanabilir. Buna karşılık element büyülerinin asgari menzili de 2 artar.",
    "content.16.22559": "Bir köpek ayakkabı çiğnerse hangi ayakkabıyı seçer? Boss Shmasser 5#.",
    "content.33.100514": "Tüm müttefiklere -2 MP",
    "content.33.158454": "-|1d[@lv]*0.24+3| [el3] HP",
    "content.33.241485": "[$1ef] [CROSSDIAGONAL]\\nHedef bir [deposit] üzerindeyse:\\n[pl]-|1d[$2$1#1]-[$1#1]| ilave HP [el1]. [CROSSDIAGONAL]\\n[pl][$2$2ef] [CROSSDIAGONAL]",
    "content.33.241490": "[$1ef] [CROSSDIAGONAL]\\nHedef bir [deposit] üzerindeyse:\\n[pl]-|1d[$2$1#1]-[$1#1]| ilave HP [el1]. [CROSSDIAGONAL]\\n[pl][$2$2ef] [CROSSDIAGONAL]",
    "content.33.290959": "Saldıran ateş kafesinin dışındaysa alınan 1.000'den fazla hasarı 1.000'e sabitler.",
    "content.33.302658": "Vandalophrenics sıkı bir grup hâlindeyken Direnç kazanır:\\n[pl]1-2 hücre uzaktaki her müttefik başına alınan hasar -%30\\n\\nÖnden doğrudan hasar aldığında:\\n[pl]Saldıranı 3 hücre çeker (saldıranın her turunda 1 kez)\\n\\nArkadan doğrudan hasar aldığında:\\n[pl]2 hücre itilir (saldıranın her turunda 1 kez)\\n\\nVandalophrenics zayıfken (Can Puanı %65'in altındayken) Verilen Hasar ve MP kazanır\\n\\nOyuncular raunda bağlı bir ceza alır\\nÇift raundlar: [st6450]\\nTek raundlar: [st6451]",
    "content.33.308093": "Yandan verilen hasar: %25\\n\\nÖnden verilen hasar: -%25",
    "content.33.327066": "Aura taşıyıcısına verilen hasar: -%20",
    "content.33.331890": "Her canavarın bir zaman anlaşması vardır\\nBir canavar öldüğünde zaman anlaşmasının etki alanında azami Can Puanının %25'i kadar hasar verilir\\n\\n2-4 hücrelik halkada zaman anlaşması",
    "content.33.334041": "YeCh'Ti'Wawa, sonraki turda buz küplerinin çevresindeki <b>3-6 hücrelik halkada</b> hasar verir.",
    "content.33.358025": "Rogue'un azami Can Puanının [$1#10]%'sine sahiptir\\n\\nYok edildiğinde veya alandaki 2. turunun sonunda patlar:\\n[pl][el1] hasar: |[lv]*0.3+2|[CIRCLE] (2)\\n[pl][caster] 1 WP\\n\\n[bomb] sonraki turun başında gelişir:\\n[pl]Patladığında %100 ilave hasar\\n[pl][caster] 1 ilave WP",
    "content.33.383013": "Vandalophrenics düzenli bir grup hâlindeyken alınan hasarı azaltır:\\n[pl]En fazla 3 hücre uzaktaki her müttefik başına alınan hasar -%30",
    "content.62.3503": "Zindan ve Mechalar - Stasis 3",
    "content.62.3504": "Zindan ve Mechalar - Stasis 4",
    "content.62.3505": "Zindan ve Mechalar - Stasis 5",
    "content.63.4958": "Ayarlanabilir seviye sistemini kullanarak seviyeni 215'e düşür ve Mineral Tower Zindanı'nın bossunu yen.",
    "content.64.1086": "1 kama bas",
    "content.64.4654": "İkinci güney köprüsü incelendi",
    "content.64.6295": "Nogord'u Sacrificial Power durumu en az 6. seviyedeyken yen",
    "content.64.9728": "Bir kostüm elde edip Lampionaute'a sızmak için 5 Encapuchonné ile savaş",
    "content.67.400": "Sevgili Ben, görünüşe göre birkaç şakacı yeni yamalanmış giysilerimi üstümden almış. Düşük sıcaklıklar ve giysisiz oluşum yüzünden bu yıl hediyeleri dağıtamayacağım. Gelecek yıldan önce her şeyi yoluna koymak için şunlara ihtiyacım var:• 1x Father Kwismas Coat• 1x Father Kwismas Cloak\\n\\n•\\n1x Father Kwismas Boots\\n\\n•\\n1x Father Kwismas Hat\tSevgiler, Father Kwismas",
    "content.67.630": "Başta bana güvenmediler ama şu lanet Mastogob beyinleri sonunda sözlerimi Bamboo Milk içer gibi içti. Jacquemart'ın 200 yıldan uzun süre önce projesine onları nasıl ikna edebildiğini artık anlıyorum...\\n\\n[...]\\n\\nİlk teslimatlar başladı. Freezepop'larımın gerçek etkisini fark ettiklerinde köylülerin en az yarısı beni \"izliyor\" olacak.\\n\\n[...]",
    "content.75.2289": "Seni çok rahatsız etmeyecekse yalnızca birazına ihtiyacım var; bir numune, anlarsın ya. Hmmmm... 10 Pumpkwinny Wool ve 10 Al Howin Emulsion yeterli olmalı!",
    "content.76.329": "1 kama mı? Üzerimde hiçbir şey yok, Poopy.",
    "content.76.4925": "Sugary Remains!",
    "content.76.6539": "3.000 kama mı? Biraz pahalı... Param olduğunda geri geleceğim.",
    "content.76.8676": "Biraz pahalı ama fazla seçeneğim yok. İşte 100.000 kaman!",
    "content.76.11781": "40 Tanukouï's Testicool getirdim!",
    "content.13.153637": "Su ve Hava iyi anlaşamaz!!",
    "content.156.209": "Bir sublimasyonun etkileri <text color=\"importantTextColor\">azami seviyeye</text> kadar biriktirilebilir. Bu seviye sublimasyonun açıklamasında belirtilir.\\n\\nSublimasyonların nadirlikleri farklı olabilir. Nadir bir sublimasyon eşyaya etkisinden 1 seviye, mitik bir sublimasyon 2 seviye, efsanevi bir sublimasyon ise 3 seviye ekler.",
    "content.156.268": "Bir dövüşçü bir engele itildiğinde veya çekildiğinde <text color=\"importantTextColor\">çarpışma</text> yaşar. Çarpışmaya neden olan kişi hedeften <text color=\"importantTextColor\">1 AP kaldırır</text>.",
    "content.16.10800": "Ortak bir kader, birbirine asla sırt çevirmeyen bir ömür\\n- Sram ikizleri",
    "content.16.11386": "Peki, parmağında bir Fleaster Wodent Ring olmasını kim hayal etmemiştir?",
    "content.16.13239": "Yeni köl-\\nşey, kocana pranga taktığın o özel gün için biçilmiş kaftan.",
    "content.16.14850": "Bu yayı geren Arachnee Embroiderer'ın, Ancestral Treechnid memnun kalmadan önce elli dokuz kez sıfırdan başladığı söylenir.",
    "content.16.15221": "Arachnee bacaklarının uğur getirdiği söylenir. İşe yaramazsa onları her zaman yiyebilirsin. Yağda kızartıldıklarında nefis bir başlangıç olurlar!",
    "content.16.15540": "Bunu önünde yel değirmeni gibi döndürürsen hiçbir Moofly'ın, hatta hiçbir şeyin, yoluna çıkmaya cesaret edemeyeceğini garanti edebilirsin.",
    "content.16.18100": "Yeni köl-\\nşey, sevgili eşine pranga taktığın o özel gün için biçilmiş kaftan.",
    "content.16.20177": "Chrome-Plated Mercury'nin yaraları iyileştirdiği söylenir. Belki de başka bir işe yarıyordur?",
    "content.16.25042": "Peki, parmağında bir Cawamel Wodent Ring olmasını kim hayal etmemiştir?",
    "content.16.26278": "Bu kostümün yaydığı cehennemî güç öylesine büyüktür ki Shushu'lar seni efendileri sanabilir.",
    "content.16.26379": "Tıpkı Phoenix gibi uluslar, Ogrest'in yol açtığı felaketlere rağmen küllerinden yeniden doğuyor. Bu göz alıcı kostümü giyerek yenilenmenin parçası ol. Ama kendini yakma!",
    "content.16.3753": "Arachnee bacaklarının uğur getirdiği söylenir. İşe yaramazsa onları her zaman yiyebilirsin. Başlangıç olarak kızartıldıklarında nefistirler!",
    "content.33.113079": "Taşıyıcı hasar alırsa:\\n- [st2388] taşıyıcısı %25 hasar alır",
    "content.33.266015": "Bu durum 2. seviyeye ulaşırsa:\\n[st131] olursun",
    "content.33.357969": "[enemy] için, [st3698] etkisi varken:\\n[pl][se] (1 tur)",
    "content.4.5628": "Zordfish'in yoluna çıkan tüm düşmanlara hasar vermesini sağlayan korkunç bir saldırı. Ah!",
    "content.47.19331": "Defolun buradan!!",
    "content.47.20842": "Merhaba. Ben Sham Moon. Ya sen?",
    "content.63.2451": "Present Xelorium'a dönebilmek için büyük bir zaman yarığından geçmen gerekecek. Explorancient'a göre burada zaman birbirine karışmış ve buradan geçen az sayıdaki Xelorium sakini delirmiş. Yine de ekibine kavuşmak için tek şansın bu.",
    "content.63.3687": "Şu iki Boowolf da onlara yardım etmemi istiyor ama Otomai'nin bana mümkün olduğunca çabuk ihtiyacı var; acele edelim.",
    "content.64.3830": "Spor Odası'ndaki Fungi Master ile konuş",
    "content.64.8195": "Ohwymi'deki Ouginak muhafızıyla konuş",
    "content.67.404": "<text align=\"center\"><b>Ve Dünyanın Başka Yerlerinde</b></text>\\n\\n- Hoodlum'lar ana gemileriyle takımadaların üzerinde dolaşıyor. Onlarla savaşırsan kimlikleri açığa çıkacak.\\n\\n- Amakna'daki Holey Ormanı artık bir deponun girişini koruyan dev bir Crackler'a ev sahipliği yapıyor.\\n\\n- Sufokia'daki Cradle bölgesine girersen aklını başına toplasan iyi olur; Dry Selachii geldi![#icon 59]",
    "content.67.425": "<text align=\"center\"><b><u>TOFU MU, YUMURTA MI?</u></b></text>\\nGazete'de dolaşan söylentiye göre <b>Masqueraider'lar</b> <b>Wakfu Çağı</b> boyunca varmış. Astrub'da ortaya çıkmalarının, yönetimi aldatıp kimliklerini gizlemeyi amaçlayan <b>büyük bir hileden</b> ibaret olduğu söyleniyor. Peki gerçekte kimler?\\n\\n[#icon 57]",
    "content.67.700": "<text align=\"center\"><b><u>BİR MİLYON ARTIK ESKİSİ KADAR ETMİYOR</u></b></text>\\n\\nTeklif sürecinin sorunsuz ilerlemesi, yani kan gölüne dönmemesi için, Bay X diyeceğimiz gerçek bir profesyonel olan baş müzayedeci Gazete okurlarına birkaç önemli kuralı hatırlatmak istiyor:\\n\\n\\n- Her lot <b>\\nbir hafta</b> boyunca tekliflere açık kalır.\\n\\n\\n- Lotlar <b>\\nayrı ayrı</b>\\n, birer hafta arayla tekliflere açılır. Her hafta <b>\\n15 Sığınak Dünyası</b> satışa çıkarılır.\\n\\n- Bir lonca yalnızca <b>\\nbir Sığınak Dünyası'na</b>\\n teklif verebilir; bunun için hâlihazırda bir Sığınak Dünyası'na sahip olmamalıdır.\\n\\n- Açılış fiyatı 100 kamadır.\\n\\n- Bir teklif verildiğinde kama tutarı lonca bankasından <b>\\nçekilir</b>\\n.\\n\\n- Teklif başka bir lonca tarafından geçildiğinde kama tutarı lonca bankasına <b>\\niade edilir</b>\\n.\\n- Yalnızca <b>Lonca Lideri</b> ve inşa <b>izni</b> bulunan üyeler teklif verebilir.\\n\\n- Teklif vermek için açık artırma arayüzündeki \"<b>Teklif Ver</b>\" düğmesine tıkla.",
    "content.67.873": " \\nGİRİŞ 215\\n\\nYaşıyorum. Ecaflip aşkına!\\nİnanması güç. Üstelik yalnızca hayatta değilim, sağlam zemindeyim! Fırtına daha çok bir kasırgayı andırıyordu ve gemiyi şiddetle savurdu. Öyle ki başım bir kirişe çarpınca anında bayılmışım. Kaptan'ın kamarasında sayısız çürük ve sıyrıkla uyandım; kamara tamamen altüst olmuştu ve lombozdan süzülen bir güneş ışını yüzümü ısıtıyordu.\\n\\nİyi haberler de tek gelmiyor. Artık Crocodyl'ların da hayatta kaldığını biliyorum.\\nBu bir hafta önceydi. Kamarayı didik didik edip seyir defterini bulmam bu kadar sürdü.",
    "content.75.1930": "Onun sihirli kazanını kullanarak geçici bir dönüşüm geçirebildiğini duydum. Neden denemiyorsun? Kazan Astrub'da, Wabbit Mezarlığı'nın yakınında. Onu bulup 4 Piece of Pumpkwin ile doldur; bu yeterli olmalı!",
    "content.75.2585": "Inhibitor'dan söz açılmışken, aslında seni tedavi ederken bütün stoğumu kullandım. Biraz daha toplamama yardım eder misin? \\nBlackspore'lar saldırırsa ona ihtiyacımız olacak!",
    "content.75.3299": "Ben Botan Ficus, bu köyün ruhani lideriyim. Ama bunun bir güç makamı olduğunu sanma. Ruhani lider olmak, kabilenin iyiliği için kendini bütünüyle adamak demektir.\\nBuradaki herkes gibi ben de bir Kanniball'ım. Ataların geleneklerine saygı gösteren ve bu mabedi dünyanın çılgınlığından koruyan son Sadida'larız.",
    "content.75.3505": "Görünüşe göre On İkiler Dünyası'nı 200 yıl önce kasıp kavuran Ogrest's Chaos sırasında Incarnam da büyük zarar gördü. Ancak Chaos burayı doğrudan etkilemedi. Küçük Ogrest'imin elindeki Primordial Dofus'lar ona buraya saldıracak kadar güç vermemişti.\\nHayır, burada daha üzücü bir şey oldu.",
    "content.75.3704": "Astrub Zaap'ını kullanıp Incarnam'a dönerek istediğin zaman beni görebilirsin.\\nBana gerçekten ihtiyacın olursa \"Otomai Finisher\"ı da etkinleştirebilirsin; vaktim olduğunda gelip bir bossu ya da canavarı yenmene yardım ederim!",
    "content.75.4355": "Aşağıdaki gerçekten Black Crow muydu?",
    "content.75.4478": "Ben Sufokia'nın baş aşçısı Fafahoff'um. Burada çoğunlukla denizden çıkan malzemeleri kullanırız ama iştahımı doyurmak için Brakmar'dan iyi et de getirtiyorum. Elimde değil; iyi bir öğün olmadan güne başlanmaz. Sipariş vermek ister misin?",
    "content.75.4586": "*Vazgeçmeden önce birkaç dakika sana bakar* Pekâlâ. Sanırım bu senin hatan değil. Üstelik Tibia-Thrasher ile adamlarının konumunu bize verdin. Kartel bununla yetinmek zorunda.",
    "content.75.5404": "Pekâlâ bir kâbus olarak yeniden bedenlenmiş olabilir. Yine de şu an durumun ne olduğunu bilmiyorum. Gerçek şu ki yok olduğu sanılan bazı iblis krallar birkaç yüzyıldır yeniden ortaya çıkıyor.\\n\\nRushu'nun otoritesi çok yakında sınanacak gibi.",
    "content.75.5585": "Ben Goomy'yim ve ailemin dönmesini bekliyorum. Babam iki hafta önce keşfe çıktı. Annem de endişelenip onu aramaya gitti.\\n\\nUslu olmamı ve onları evde beklememi söyledi ama buraya gelirsem onları bulabileceğimi düşündüm.",
    "content.75.5682": "Anlıyorum. Raeliss, kralımızı On İkililerin öldürdüğünü sanmış. Geçen gemilere saldırmasının nedeni bu olmalı.\\n\\n*Spriggiss duraksar*\\n\\nArtık Raeliss de son dev olan kralımız da yok. Abyssal Creeper'ları barış ve uyum yoluna yöneltecek kimse kalmadı.",
    "content.75.5741": "Pekâlâ. Bildiğim tek şey Alibert'in bu durumla başa çıkabilecek birini aradığı. Emelka Ormanı'nda onunla görüşmelisin; orada gözcülük ediyor olmalı. Son zamanlarda Prancing Chimera'larla bir sorunu var gibi.\\n\\nGobball yahnisini mutlaka dene; On İkiler Dünyası'nın en iyisidir!",
    "content.75.5892": "Anlıyorum!\\n\\n*Sana yaklaşır ve neşeyle gülümsemeyi sürdürerek gözlerinin içine bakar*\\n\\nBen Alia. Sana seve seve yardım ederim. Neye ihtiyacın var?",
    "content.75.6182": "Osamosa'nın, Master of Beasts'in bütün deneylerini yürüttüğü yer olduğu söylenir. O boyuttaki ekosistem öylesine eşsizmiş ki orada kalan yaratıklar inanılmaz bir canlılık ve yetenek geliştirirmiş. Büyükannem bu dünyadaki bütün canlıların, On İkiler Dünyası'nda bedenlenmeden önce Osamosa'nın bahçelerinde başladığını söylerdi.",
    "content.75.6295": "Arlemia'yı mı diyorsun? Evet, hatırlıyorum. Babasıyla birlikteydi.\\n\\nBütün bu durum, On İkililerle Shushu'ların gerçekten bir arada yaşayabileceğinin kanıtı sayılır.",
    "content.75.6422": "Gördüğüm tüm kanıtlar Crocodyl'ların adadan kaybolduğunu gösteriyor. İlk incelemelerime göre izler en fazla bir yüzyıl öncesine ait.\\n\\n*Lebbocq'un parlayan gözlerinde arkaosoloji kıvılcımını tanırsın*",
    "content.75.6447": "Demek Crocodyl'ları Bwork'ler yok etti. Bu öykünün Crocoburio'nun kendisi hakkında olması ilginç. Kılıç hâlâ adada olabilir!\\nŞimdilik beni bu hücreden çıkarabilir misin?",
    "content.75.6572": "Sanırım Nox'la savaşmamıza yardım etmeye hazır! Sana borçlu olduklarını söylüyor.\\n\\nTimo'nun hâlâ birkaç şeytani gücü var gibi.",
    "content.75.6941": "Ah! Bana yemek dersi vermek isteyen bir{[1*]?:} maceracı{[1*]?:}. Çok ilginç.\\n\\nNeler teslim edebileceğine bakalım.",
    "content.75.7083": "Pekâlâ. Görünüşe göre her şey bitti.",
    "content.75.7087": "Timo'nun tutulduğu hapishane burası olmalı.\\n\\nBurada kalan duygular Dofus'ta bir tepki uyandırıyor mu?",
    "content.75.7214": "Elinden geleni yaptığın söylenebilir ama Aguabrial hâlâ aklı başına gelmiş görünmüyor. Bir haber alırsam sana bildiririm.",
    "content.76.10016": "Dreggon'ları uyutanın bu küçük yaratık olduğunu düşünüyorum.",
    "content.76.11517": "Belki bütün Blightopard'larla kesin olarak ilgilenirsem ormanı yeniden dikebilirsin. Büyük Ruhun da mutlu olur!",
    "content.76.11688": "Pekâlâ, Ohwymi'de her şey yolundaysa en azından bir ada iyi durumda demektir. Hazırlanmana izin vereyim. Kendini fazla tehlikeye atma; sporların sana ihtiyacı var!",
    "content.76.12094": "Anlıyorum. İtiraf etmeliyim ki Xelor'un insanların kaderleriyle bu denli oynamasının pek{[1*]?:} büyük{[1*]?:} hayranı değilim. Bundan hastalıklı bir zevk alıyor gibi.",
    "content.76.12524": "Sanırım Arlemia'nın hâlâ zamana ihtiyacı var.",
    "content.76.13120": "Onlar gerçekten senin halkın mı? Abyssal Creeper'ların toplumsal ilkelerine uyum sağlasaydın bugün olduğun kişiyi kaybederdin. Yolculuğunu anlatırken benimle zaman geçirdin; bu sana yakışıyor. Kendi yolunu izledin ve doğru olanı yaptın. Artık herkesin mirasını taşımalısın.",
    "content.76.14215": "Bu görevim için yararlı. Onunla ne yapmam gerektiğini henüz bilmiyorum. Ama Lebbocq hayal kırıklığına uğrayacak!",
    "content.76.14281": "Gerçekten mi? İlginç. Şimdiye dek burada yalnızca Bwork gördüm.",
    "content.76.8287": "Ee? Peki ya Orichalcum?",
    "content.76.9646": "Draconic Ocarina'dan söz ediyorsan bu yarığı geçmek için onu zaten kullandım!",
    "content.76.9648": "Mollusky Egg'u buldum.",
    "content.76.9658": "Selachii Egg'i buldum.",
    "content.76.9721": "Schnek Egg'i buldum.",
    "encyclopedia.world.loot.monster.level": "[#1] seviyesindeki canavarlardan.",
    "encyclopedia.world.loot.monster.level.range": "[#1] {[32767=2]?ve üzeri:[#2] seviyesine kadar} canavarlardan.",
    "nation.criminalIn": "[#1], [#2] topluluğundasın",
    "nation.playerCriminal": "[#2], [#1] nezdindeki durumun",
    "notification.guildSelfQuitText": "{[~2]?[#2]:Sen} artık [#1] loncasının bir parçası değilsin.",
    "quest.DDCH0.pandora.Corniche05": "Astrub'a dönmeyi tercih ediyorsan şimdi söyle. Kuleye girdikten sonra geri dönüş yok!",
    "quest.amakna.mercenary.riktuselite.03.01": "Buradaki raylar muhtemelen Crackler depremleri yüzünden kırılmış. Burası çıkmaz gibi.",
    "quest.brume.coeur.02.22": "Pekâlâ. Her zamanki gibi önce adamları, sonra büyük bossu!",
    "quest.brume.ebene.01.04": "Sana sunabileceğim{[1*]?:} tek{[1*]?:} şeyi vereceğim: özgürlüğünü.",
    "quest.brume.horlogetourne.02.16": "Bu kibir değil. Doğrusu Alraune ile ben bunun yüzünden acı çektik. ",
    "quest.brume.intro.01.27": "Ben Julpi. Direnişin lideriyim.",
    "quest.huppermage.dortoirs.02": "Yeni gelen uyandı. On{[1*]?u:u} yakalayın!{[1*]?:}{[1*]?:}{[1*]?:}\\nOn{[1*]?u:u} kaçırmayın!!",
    "quest.karn.00.03": "Geriye Boowolf Açıklığı kalıyor. Oradan başlayalım.",
    "quest.nations.ch04.end.cine.makamomie.10": "Şimdi yalnızca Orichalcum'u ondan almamız gerekiyor!",
    "quest.nations.ch05.cine.temple.transfomimi.02": "Ah, küçük bir Gemlin hâlindeyken ne kadar da sevimli!",
    "quest.neo.07.09": "Ama [#name], Neo Boss'ları yenmeyi başardı! Alkışlayalım!",
    "quest.ri.02.02": "Ben Airyna. Dojoma hoş geldin.",
    "quest.wabbit.lenald.dojo.04": "**Oğlu mu? Loyal Lenald'ı mı kastediyor?",
    "quest.zinit.ch4.cine.colere.ogrest.08": "Ne? Ogrest'e mi dönüştün? Aguabrial da seninle yüzleşti mi?",
    "content.4.8149": "The Voodoll artık bir düşmana bağlanamaz; ancak Sadida'nın diğer oyuncak bebeklerini desteklemek için hareketlilik ve menzil kazanır.",
    "quest.astrub.chacha.24": "Dikkat!!!",
    "quest.astrub.chacha.27": "Usta Goultard, hayır!!!",
    "quest.astrub.ullu.2": "SEN!!! Sensin!",
    "quest.astrub.ullu.6": "OGREST'İ YENMEK VAR!!!",
    "quest.saharach.comportementCacterre4": "Ponk ponk poiiiiiink!!!",
    "content.75.3892": "İşte buradasın! Kehanetin Seçilmiş Kişisi{[1*] ?e:}!",
    "content.75.3924": "Ah, doğru... Rol yaptığım kadar \"tanrısal\" değilim. Buraya kadar gelmeni sağlamak için hikâyeyi biraz süslemenin daha iyi olduğunu anlamalısın. Kehanet ise bazı açılardan doğru. Geçmişte benimle konuşmaya gelen{[1*] ?e:} kişi sen miydin?",
    "content.75.3939": "Ne? Adamlarım sana zarar mı verdi? Ah, zavallıcık{[1*] ?e:}... Biraz şeker ister misin?",
    "content.75.3960": "Aslında seni yanlış değerlendirdiğimi itiraf etmeliyim{[1*] ?e:}. Uzun zaman önce ölmüş{[1*] ?e:} ya da kaçıp gitmiş{[1*] ?e:} olacağını sanmıştım. Ama beni görmeye dönüp duruyorsun. Başka biri şimdiye dek dünyanın dört bir yanına saçılmış küçük parçalara dönüşürdü. Sanırım sana karşı bir zaaf geliştirmeye başlıyorum... ",
    "content.76.9891": "Evet, ama ben köle{[1*] ?e:} değilim!",
    "content.76.9936": "Hayır, lütfen! İyi davranacağım{[1*] ?le:}.",
    "mercenaries.help": "<u><b>Paralı Asker Karakolları</b></u>\\n \\n \\nBurada bölgenizdeki bütün paralı asker sözleşmelerini görebilir ve tamamlamak için gereken koşulları karşılıyorsanız kabul edebilirsiniz.\\n\\n<b color=\"FF0000red</b> sözleşme, sözleşmeyi yerine getirmek için <b>gereken koşulları karşılamadığınızı</b> gösterir.\\nBu koşulların ayrıntıları için sözleşme açıklamasına bakın veya koşulların özetini baloncukta görmek için listede sözleşme adının üzerine gelin.\\n\\n<b color=\"FFFFFF\">Beyaz</b> sözleşme, gereken koşulları karşıladığınızı ve <b>sözleşmeyi kabul edebileceğinizi</b> gösterir.\\n\\n<b color=\"ffde6c\">Sarı</b> sözleşme, sözleşmeyi <b>zaten kabul ettiğinizi</b> ancak <b>henüz tamamlamadığınızı</b> gösterir.\\n\\n<b color=\"4de639\">Yeşil</b> sözleşme, sözleşmeyi <b>zaten kabul edip tamamladığınızı</b> gösterir.",
    "content.6.630": "Bwork Beer Fıçısı: Bwork'ü içmeye zorlamak için yok et",
    "content.6.633": "Bwork Beer Fıçısı: Bwork'leri içmeye zorlamak için yok et",
    "content.6.1240": "Küçük Ogrest's Tear",
    "content.6.1244": "Küçük Ogrest's Tear",
    "content.6.1412": "Orbital Strike - Hedef",
    "content.6.1809": "Gecikmeli Burning Bomb",
    "content.6.1811": "Gecikmeli Blinding Bomb",
    "content.6.1952": "Sacred Fire Kılıcı",
    "content.6.1958": "Wakfu Shot Başlangıcı",
    "content.8.1732": "Cold Blood'a Susamışlık",
    "content.8.2026": "Lethal Dancefloor Hazırlığı",
    "content.8.2103": "Mechanikal Prison'a Karşı Bağışıklık",
    "content.8.2253": "Sandrine Al Howin Costume",
    "content.8.2499": "Otomai's Disciple Costume - İstifçi",
    "content.8.2989": "Lock Picking İlerlemesi",
    "content.8.3444": "Health Steal Kombosu",
    "content.8.3579": "Değiştirilmiş Windy Armor",
    "content.8.3585": "Darkness Knight Yeteneği",
    "content.8.4262": "Boomerang Hammer (Bayrak)",
    "content.8.4514": "Stasisleşmiş Dragon Form",
    "content.8.5456": "Bayrak - Big Api Theory",
    "content.8.5852": "Blople Rain - Hasar Cezası",
    "content.8.6139": "Bağlantı: Defensive Stance",
    "content.8.6332": "Crashing Wave Kalkanı",
    "content.8.6333": "Telluric Whack Kalkanı",
    "content.8.6334": "Defensive Orb Kalkanı",
    "content.8.6355": "Crashing Wave Kalkanı",
    "content.8.6356": "Telluric Whack Kalkanı",
    "content.8.6357": "Defensive Orb Kalkanı",
    "content.8.6367": "Güçlendirilmiş Antlerus Blow",
    "content.8.6622": "Keep in Contact - Bonus",
    "content.8.6623": "Keep in Contact - Ceza",
    "content.8.6626": "Cautious Protector - Bonus",
    "content.8.6627": "Cautious Protector - Ceza",
    "content.8.6710": "Ancestral Energy - Bonus",
    "content.8.6732": "Turquoise Dofus - Bonus",
    "content.8.7045": "Anathar's Mark - Health Steal",
    "content.8.7046": "Anathar's Mark - Geri İtme",
    "content.8.7047": "Anathar's Mark - Çekme",
    "content.8.7594": "Clammy Tentattackle - Direnç Cezası",
    "content.8.7820": "Celestial Portal - Sayaç",
    "content.8.8730": "Sacred Fire Kılıcı",
    "content.8.8785": "Ebony Dofus - Menzilli Yük",
    "content.8.8786": "Ebony Dofus - Yakın Dövüş Yükü",
    "content.8.8788": "Ebony Dofus - Yenilenme Süresi",
    "content.8.8860": "Clockmaker's Pact yerine getirildi",
    "content.8.8971": "Eliatrope Energy Battery",
    "content.8.9007": "Feca Amulet - Bekleme Süresi",
    "content.8.9012": "Spanner's Wrench - Bekleme Süresi",
    "content.8.9013": "Shushu Sword - Bekleme Süresi",
    "content.8.9014": "Bworkana Clan Talisman - Bekleme Süresi",
    "content.8.9015": "Starvannah Brush - Bekleme Süresi",
    "content.8.9016": "Starvannah Talisman - Bekleme Süresi",
    "content.8.9017": "Ebony Dofus - Bekleme Süresi",
    "content.8.9262": "Chafer Legs Dönüşümü",
    "content.8.9268": "Pandawa Cub Dönüşümü",
    "content.33.36691": "Guard Costume'u verir",
    "content.33.64888": "Farmer's Wife Set'i verir",
    "content.33.64889": "Little Pirate Set'i verir",
    "content.33.64893": "Sacred Bow Meow Set'i verir",
    "content.33.64896": "Farmer Set'i verir",
    "content.33.64897": "Set of the Rising Sun'ı verir",
    "content.33.65725": "Flaming Torch yirmi dakika boyunca etkin.",
    "content.33.86016": "Saldırıya uğradığında Feather Explosion oluşturur",
    "content.33.86746": "[#1] [el1] Energy Charge{[=1]?:s}",
    "content.33.86754": "[#1] [el4] Energy Charge{[=1]?:s}",
    "content.33.86760": "[#1] [el2] Energy Charge{[=1]?:s}",
    "content.33.86766": "[#1] [el3] Energy Charge{[=1]?:s}",
    "content.33.89016": "[pl]Turun sonunda Brrrbley Spear'ları bir müttefikin yanına ışınlar",
    "content.33.97577": "Bilby Queen'in Lethal Sides tarafına dönük durmayın",
    "content.33.107880": "Rastgele bir Bwork Artifact ortaya çıkarır",
    "content.33.108624": "Spring Has Sprung Costume'u verir",
    "content.33.109140": "Little Farmer Costume'u verir",
    "content.33.112605": "Günlük Bilgelik ve Prospecting Candy kazanımı",
    "content.33.114356": "All or Nothing:\\n[pl]Tüm canavarlar sonraki tur döngüsü başlamadan önce ölmelidir",
    "content.33.114357": "Sacred Bow Meow Set'i verir",
    "content.33.116381": "Onu yiyen Bulldagger'ı yavaşlatacak bir Poisoned Bone yerleştirir",
    "content.33.146122": "Pandawa Barrel'ın normal Can Puanı gibi işleyen Litreleri vardır.\\nBazı büyüler Fıçı taşınırken veya Fıçıya kullanıldığında ek etkiler oluşturur.\\nPandawa turun sonunda kendi Fıçısını taşıyorsa Fıçıdan içer, Litrelerinin %5'ini tüketir ve ardından [st3300] ile [st3301] durumlarına girer.",
    "content.33.147270": "Pandawa Barrel'ın normal Can Puanı gibi işleyen Litreleri vardır.\\nBazı büyüler Fıçı taşınırken veya Fıçıya kullanıldığında ek etkiler oluşturur.\\nPandawa turun sonunda kendi Fıçısını taşıyorsa Fıçıdan içer, Litrelerinin %5'ini tüketir ve ardından [st3300] ile [st3301] durumlarına girer.",
    "content.33.153692": "Windy Armor, Steel Beak'in rakiplerinin stratejilerine etkili biçimde karşılık vermesini sağlar.",
    "content.33.155176": "Stony Skin daha da sertleşiyor...",
    "content.33.158095": "Set of the Rising Sun'ı verir",
    "content.33.165559": "Osamodas, müttefikiyle Animal Link kurmuştur",
    "content.33.167750": "Animal Link bedeli [#1] AP azalır",
    "content.33.179798": "Hedef, arkadan yapılacak bir sonraki saldırıda Yıkıcı Hasar vermek üzere Eliotrope tarafından Wakfu Imprint ile işaretlenir.",
    "content.33.244502": "The God Ecaflip dövüşün sonunda müdahale edebilir",
    "content.33.266780": "Kızıl güneş Shadofang'ın Cast Shadow etkisini oluşturur",
    "content.33.266901": "Kızıl güneş Shadofang'ın Cast Shadow etkisini oluşturur\\nGüneşin dönüşü hızlanır",
    "content.33.269669": "Kitsune's Flame yolunu aydınlatır.",
    "content.33.282594": "Tur başında Sudden Death durumuna girer:\\n[pl]Canı 1'e düşer\\n[pl]Kaybettiği Canın yarısı kadar Zırh kazanır",
    "content.33.312608": "Hedefi bir Time Rift üzerine ışınlar",
    "content.33.314498": "Against the Clock tarafından hedef alınamaz",
    "content.33.319015": "Health Steal: [#7]%",
    "content.33.332317": "Full Moon\\n\\n[se]",
    "content.33.334589": "Soul Aspiration (7529)",
    "content.33.357859": "All or Nothing:\\n[pl][fighter] [$2ef]\\n[pl][fighter] ve [caster] [$2ef]",
    "content.33.357862": "All or Nothing:\\n[pl][fighter] [$2ef]\\n[pl][fighter] ve [caster] [$2ef]",
    "content.33.371986": "Still Life üzerine basıldığında:\\n[pl][$1ef]\\n[pl]2 Menzil (1 tur)",
    "content.33.372016": "2 bomba aynı hizadaysa:\\n[pl]Bir [st5582] oluşturulur\\n\\nTuruna [st5582] üzerinde başlayan savaşçılar hasar alır\\n\\nBir [st5582] etkinleştirildiğinde, Powder Wall oluşturan [bomb] ögeleri:\\n[pl]1 seviye kaybeder\\n[pl]1. seviyenin altına düşünce patlar",
    "content.33.374622": "Bir tutam tuz ve biber, biraz maydanoz, birkaç diş sarımsak ve bolca Nolifis likörü ekleyip ısıt; damakları şenlendirecek bir maceracı salata sosu hazır!\\n\\nZomkin, deneyimli savaşçılara <b>Cook Up</b> büyüsünü kullanır",
    "content.33.377431": "[st3616] çağırır\\n[pl]Hedefi The Voodoll'a bağlar: [st3857]\\n[pl]The Voodoll 2 tur boyunca sahada kalır\\n[pl]Çağrılabilmesi için boş bir hücre gerekir",
    "content.33.378185": "[st3595] çağırır:\\n[pl]Diğer bütün [puppet] varlıklarını feda eder\\n[pl]<b>The Ultra-Powerful</b> onların yeteneklerini kazanır\\n[pl]<b>The Ultra-Powerful</b> [st3624] kazanmaz\\n\\nTakım başına en fazla 1 <b>Ultra-Powerful</b>",
    "content.33.380515": "Toross Mordal artık Stasmic Boom kullanamaz",
    "content.33.380527": "Her tur savaş alanında yalnızca bir Wakfu Well belirir",
    "content.33.384945": "[$1ef]\\nAsgari büyü Menzili 1 olur\\nBüyü Menzili 3'ün üzerine çıkmaz\\n(Excavation, Prime of Life ve Seismic Wealth hariç)",
    "content.33.391399": "Elemental Cycle: Timo'nun ve oyuncuların turu sonunda tetiklenir",
    "content.33.401634": "<b>Sermon of Time</b> ve <b>The Inescapable</b> büyülerinin kilidini açar\\nTur başında <b>Sermon of Time</b> büyüsünü kullanır\\n\\nTur sonunda durum 1 seviye kazanır\\n\\nBir oyuncu Nox görüş hattındayken ve en az 5 hücre uzaktayken ona hasar verirse:\\n[pl][st9027] (+2 Sv.)",
    "content.33.407439": "<b>Sermon of Time</b> ve <b>The Inescapable</b> büyülerinin kilidini açar\\nTur başında <b>Sermon of Time</b> büyüsünü kullanır",
    "content.33.413075": "Bir Masked Spirit çağırır (Masqueraider'ın azami Can Puanının %40'ı)\\n[pl]Masqueraider'ın özelliklerini kopyalar\\n[pl]6 AP + Masqueraider'ın kullanılmamış AP'sine sahiptir (en fazla 6)\\n[pl]6 WP'ye sahiptir\\n[pl]Masqueraider, Spirit'in aldığı tüm hasarı da alır\\n[pl]Kilitleyemez",
    "content.156.457": "Küp dövüşün merkezindedir. <text color=\"importantTextColor\">Wakfu Yükü</text> 1'den 24'e kadar değişir. Bu durum tüm savaşçıların verdiği ve uğradığı hasarı etkiler. 12'nin üzerinde tüm hasar artar (en fazla +%360). 12'nin altında tüm hasar azalır (en fazla -%55).",
    "content.156.530": "<u><text align=\"center\">Chaos Avcısı: Boss İstilası!</text></u>\\nBir hafta boyunca (hatta sonrasında da!) bir dizi <text color=\"importantTextColor\">simgeleşmiş boss</text> zindanlarından çıkıp On İkiler Dünyası'nı istila ediyor...\\n5 Mayıs Salı günü saat 08.00'e (CEST) kadar ciddi bir av sizi bekliyor. On İkiler Dünyası'nda Aguabrial'ı aramaya koyulun; onu bulduğunuzda sizi dört özdeş bosstan oluşan gruplara karşı savaşa sürükleyecek!",
    "content.33.107820": "Can Puanı %33'ten az olduğunda:\\n[pl][#1]% Blok",
    "content.33.108946": "Eksik Can Puanının her %1'i için +0.0[#1] Element Direnci",
    "content.33.108983": "Eksik Can Puanının her %1'i için +0[#1] Element Direnci",
    "content.33.108996": "Eksik Can Puanının her %1'i için +0.0[#1] Ustalık",
    "content.33.108997": "Eksik Can Puanının her %1'i için +0[#1] Ustalık",
    "content.33.109109": "Can Puanı %50'den az olduğunda:\\n[pl][#1]% Blok",
    "content.33.109622": "Can Puanı %25'ten az olduğunda:\\n[pl][#1]% Blok",
    "content.33.109627": "Can Puanı %66'dan az olduğunda:\\n[pl][#1]% Blok",
    "content.33.109632": "Can Puanı %75'ten az olduğunda:\\n[pl][#1]% Blok",
    "content.33.164584": "[el4] büyüler verilen hasarın [$1#1]%'ini çalar\\n15. seviyede: [st3818]",
    "content.33.170532": "+|[#10.2]*100|% Can Puanı kadar Zırh",
    "content.33.171086": "Yakındaki müttefiklerin aldığı hasarın |[#7.1]*100|%'ünü kendisi için İyileştirmeye dönüştürür",
    "content.33.176385": "Mecha'nın azami Can Puanının |[#10.1]*100|%'ü kadar Koruma",
    "content.33.193523": "Taşıyıcı hasar verdiğinde:\\n[pl]Verilen hasarın |[#7d2]*100|%'ünü çalar",
    "content.33.197840": "Uğranılan hasarın |[#7d2]*100|%'ünü saldırgana geri verir",
    "content.33.233334": "Tepkilerin gücüne +|0d[#1#2]|%",
    "content.33.240837": "|2d[lv]*0.04|% Kritik Vuruş",
    "content.33.240880": "|2d[lv]*0.07|% Kritik Vuruş",
    "content.33.241078": "Mevcut Can Puanının |[#10d2]*100|%'ünü tüketip Ouginak'a verir",
    "content.33.282349": "Alınan hasarın |[#7d2]*100|%'ünü saldırgana geri verir",
    "content.33.282351": "Alınan hasarın |[#7d2]*100|%'ünü saldırgana geri verir",
    "content.33.282353": "Alınan hasarın |[#7d2]*100|%'ünü saldırgana geri verir",
    "content.33.283240": "Can Puanı %90'ın üzerindeyken:\\n[pl]Element Ustalığı olarak seviyenin <b>[$1#8]%</b>'i",
    "content.33.283401": "Can Puanı %50'nin altındayken:\\n[pl]Kilitleme olarak seviyenin <b>[$1#8]%</b>'i",
    "content.33.298803": "Bir hasar büyüsünden etkilendiğinde Can Puanı %50'nin altındaysa:\\n[pl]<b>Azami Can Puanının %8'i kadar Zırh</b>",
    "content.33.304237": "Bir düşmandan alınan hasarın |[#7.2]*100|%'ünü Feca'ya yönlendirir",
    "content.33.328146": "Bir düşmandan alınan hasarın |[#7.2]*100|%'ünü Boohemoth'a yönlendirir",
    "content.33.340933": "Strawberry Jellies bu varlığa |[#1]*10|% ek hasar verir",
    "content.33.344030": "Topun verdiği hasar -%50\\n\\nTop, etkin elemente göre ek etkilere sahiptir:\\n[pl][el1]: [st756] uygular (+2 sv.) (Topun her seviyesi için +1)\\n[pl][el2]: Düşmanları 2 hücre iter (Topun her seviyesi için +1)\\n[pl][el3]: Müttefiklere Zırh verir (Foggernaut'ın azami Can Puanının %3'ü + Topun her seviyesi için +2)",
    "content.33.344903": "Can Puanı %90'ın üzerindeyken:\\n[pl]<b>[$1$1#1]%</b> Blok",
    "content.33.368147": "Eniripsa'nın Can Puanı &gt;= %80 ise:\\n[pl]Yapılan İyileştirmeler %30 artar\\n[pl]Eniripsa, yaptığı İyileştirmelerin %10'u kadar hasar alır",
    "content.33.378095": "Tur başında:\\n[pl][$1ef]\\n[pl][$2ef]\\n\\n[caster] azami seviyesinin %200'ü",
    "content.33.378097": "Tur başında:\\n[pl][$1ef]\\n[pl][$2ef]\\n\\n[caster] azami seviyesinin %200'ü",
    "content.33.389702": "Alınan yakın dövüş hasarını %50 azaltır\\n\\nMenzilden verilen hasar: %300",
    "content.33.389703": "Alınan menzilli hasarı %50 azaltır\\n\\nYakın dövüşte verilen hasar: %300",
    "content.33.394859": "Taşıyıcı bir elementte hasar verirse bir sonraki büyü için diğer elementlerde Verilen Hasar ve Yapılan İyileştirmeler +%15 artar.\\n\\nYalnızca büyünün verdiği ilk hasar satırı dikkate alınır.",
    "content.33.398310": "Alınan doğrudan hasarın |[#7.2]*100|%'ünü bir [enemy] düşmandan Iop'a yönlendirir",
    "content.33.65962": "Hasar alındığında:\\n[pl][pr]% olasılıkla 1 AP kazanır",
    "content.33.71130": "Hasarın |[#7.3]*100|%'ünü yansıtır",
    "content.64.11301": "Yumurta Mağarası'ndaki Grambo'lara 10 Ancestral Essence götür",
    "content.64.11087": "Astrub işçilerinin dikilitaşına tek seferde tam 20 Ash Wood yerleştir",
    "content.64.11093": "Astrub işçilerinin dikilitaşına tek seferde tam 20 Iron Ore yerleştir",
    "content.64.11095": "Astrub işçilerinin dikilitaşına tek seferde tam 20 Wheat Straw yerleştir",
    "content.64.11034": "Trool Fuarı'ndaki Sebsokk'a 20 Hazel Wood ver",
    "content.64.11057": "Trool Fuarı'ndaki Sebsokk'a 50 Magic Kwismas Tree Wood ver",
    "content.64.10759": "Sindrya'ya 25 Marmalot Wood götür",
    "content.64.11247": "5 Mystical Leather ve 10 Coarse Fiber getir",
    "content.64.11297": "Yumurta Mağarası'ndaki Grambo'lara 30 Sea Boss götür",
    "content.64.11074": "Laura Craft'a 10 Primal Skin götür",
    "content.64.1623": "Weapons Master's Seal üret",
    "content.64.2471": "Milkar'ı Hunter's Instinct durumu 3. seviyedeyken yen",
    "content.64.2744": "Li'l Owain's Armor'ı ara",
    "content.64.4443": "Avcılar Loncası'na 10 Moskito Wings götür",
    "content.64.4505": "Avcılar Loncası'na 10 Dark Roots götür",
    "content.64.6060": "* 1x Basic Handle (Silah Ustası)",
    "content.64.736": "1 Basic Flour üret",
    "content.76.3788": "İstersen sana 25 Iron Ore getirebilirim.",
    "content.76.5778": "Bir Albino Schnek Egg!",
    "content.76.5891": "Elbette. İşte istediğin 10 Zomkin Juice.",
    "content.76.6193": "İstediğin bütün Juicy Sap bende.",
    "content.76.6980": "Şimdilik gidip sana biraz Chafer Essence bulacağım.",
    "content.76.6983": "Chafer Essence mı? Çocuk oyuncağı. İhtiyacın olduğu kadarını getiririm.",
    "content.76.8662": "Bläck Skäte, korkunç bir canavar! İçimden bir ses bunun iyi olacağını söylüyor.\\nSana on Bläck Sänd getireceğim!",
    "content.76.9020": "Evet, Royal Tofu Feather bende.",
    "content.76.9022": "Evet, Royal Feather bende.",
    "companionBackgroundText.2832": "Kaybolan uyumu geri getirip Krosmoz'da düzeni yeniden kurmayı üstlenirsen, bunu başaracak karizmaya sahip olsan iyi olur! Multimen'in lideri Lumino, kardeşleri ya da müttefikleri en ufak yara aldığında her zaman onlarla ilgilenir. Zayıfların, ezilenlerin ve yardıma muhtaçların savunucusu olan Lumino, cömert olduğu kadar parlak ve hayat doludur. Aslında Lumino'nun tek kusuru, göz kamaştırıcı portresindeki tek kara leke kardeşi Shadow'dur...",
    "content.47.19327": "OLASI CEVAPLAR: LÜTFEN KENARA ÇEKİL::: YOLUMDAN ÇEKİL! ::: DEFOL BURADAN!! ::: KEMİKLERİNİ EZECEĞİM!!! ::: YOK ET!!! ::: ARTIK BİRİNCİL HEDEFİMSİN!!!",
    "content.75.3435": "Küçük değil!\\nSadece... ...farklı. Onu da beni de özel yapan bu.\\nOcarina'ya gelince, bu bir aile yadigârı. Ogrest Kaosu'ndan çok daha öncesinden beri nesillerdir onun koruyucusuyuz.\\nOnu ellerimde tuttuğumda Osamodas'ın tüm gücünün... şey, kendi gücümün içimde yükseldiğini hissediyorum. Önceki bir bedenlenmemde bana ait olmalı!",
    "content.75.4800": "Vay canına, ne saçmalıyorsun? Beni hayal kırıklığına uğrattın dostum{[1*]?:}. Pek parlak olmadığını biliyordum ama... vay canına. Bu hayatımda duyduğum en aptalca şey olmalı. İnsanları böyle yargılayan sensin; sonra gelip bana ahlaktan mı söz ediyorsun? Bu gerçekten çok yanlış.\\n\\nHer neyse, sanırım bu seferlik iyiliğine karşılık vereceğim.",
    "content.76.5501": "Seni üzmek istemem ama... *korkutucu bakış*...a-ama... Gerçekten çok güzel bir cildin var! Gidip sana biraz bulacağım!",
    "content.76.6763": "Lanet olsun... ...Gerçekten...",
    "quest.nations.ch03.feedback.bookbad01": "** \"Boxford Dictationary, Cilt XXXVI\"... ...\"Daha fazla tanım mı istiyorsun? Al sana\"...",
    "quest.nations.ch03.feedback.bookbad03": "** \"Egzotik Zoomoloji, Cilt XXII\"... ...\"Wabbit Taksonomisi\"",
    "quest.nations.ch03.feedback.bookbad06": "** \"Brakmar Tarihi, Cilt IV\"... ...\"Kılıçlar ve gözyaşları\"",
    "quest.nations.ch03.feedback.bookbad09": "** \"Tarikat Derlemesi, Cilt XI\"... ...\"Ogrest Tarikatı ve Dathura'nın Kız Kardeşleri\"",
    "quest.nations.ch03.feedback.bookbad10": "** \"Ogrest Kaosu Haberlerinin Özeti\"... ...\"Taze olmayan ama hâlâ göz yaşartan haberler\"",
    "quest.nations.ch03.feedback.bookbad12": "** \"Gri Ay Günlükleri, Cilt XIV\"... ...\"Vissemeryd ve Orkinosun açlığı\"",
    "quest.nations.ch03.feedback.bookbad13": "** \"Incarnam'dan Externam'a\"... ...\"Sıradan bir On İkilinin yaşamı\"",
    "quest.nations.ch03.feedback.encyclosphero": "** \"Spherolithic Encyclopedia\"... ...\"Yarıçap, çevre ve sinüzoidallik\"...",
    "content.67.1018": "Miyav!!!\\n\\nBu kahrolası efsanevi eşyanın peşindeyken bir Ecaflip canını az kalsın kaybediyordum.\\n\\nBrakmar'daki Flask Garden'da Cap'n Scoundrel'ı blackjackte yenmek üzereydim ki birden sekiz Amaknalı çiftçi bize saldırdı! Destansı bir çatışmadan sonra Scoundrel ile ben ayakta kalmıştık, fakat ufukta çılgın bir çiftçi sürüsü görünüyordu. Zıplayan denizanaları! İşte o anda hazinemi, her şeyin başladığı bankın yakınındaki kuyunun arkasına sakladım. Sonra da... canımı kurtarmak için kaçtım.\\n\\nO günden beri Scoundrel'ı görmedim.",
    "content.67.417": "Miyav!!!\\n\\nBu kahrolası efsanevi eşyanın peşindeyken bir Ecaflip canını az kalsın kaybediyordum.\\n\\nBrakmar'daki Flask Garden'da Cap'n Scoundrel'ı blackjackte yenmek üzereydim ki birden sekiz Amaknalı çiftçi bize saldırdı! Destansı bir çatışmadan sonra Scoundrel ile ben ayakta kalmıştık, fakat ufukta çılgın bir çiftçi sürüsü görünüyordu. Zıplayan denizanaları! İşte o anda hazinemi, her şeyin başladığı bankın yakınındaki kuyunun arkasına sakladım. Sonra da... canımı kurtarmak için kaçtım.\\n\\nO günden beri Scoundrel'ı görmedim.",
    "content.67.446": "\\n \\n \\n 158 numaralı Formül - <i>Kuzey Chafer'ları - sütun 5</i> (296 numune) - Başarılı - etkin durum 8 saatten uzun süre kararlı kaldı\\n\\n254 numaralı Formül - <i>Kuzey Chafer'ları - sütun 2</i> (271 numune) - Tam Başarısızlık - bütün numuneler kaybedildi - Chafer tozu kullanılmamalı!\\n\\n782 numaralı Formül - <i>Öfkeli Boohemoth</i> (1 numune) - Tam Başarısızlık - numune kaçtı - Tür zarar görmüyor gibi",
    "content.16.14986": "Bu inanılmaz Trinket Box'ta Tofu Kardeşliği üyelerinden hangisinin figürünü bulacağını kim bilebilir?",
    "content.16.18003": "Bu parçalardan 100 tane topla ve Nettlez pelerini oluştur.",
    "content.16.25093": "Bu parçalardan 100 tane topla ve Mori Memento oluştur. Ancak eşyayı üretebilmek için önce bir \"Mori Memento\" taslağı gerekir.",
    "content.16.25094": "Bu parçalardan 100 tane topla ve Ougaat oluştur. Ancak eşyayı üretebilmek için önce bir \"Ougaat\" taslağı gerekir.",
    "content.16.26589": "Bu parçalardan 100 tane topla ve Grazor pelerini oluştur.",
    "content.16.31585": "Bu parçalardan 100 tane topla ve Toross's Blade çift elli kılıcını oluştur.",
    "incarnam.cinematic.tuto1.0": "incarnam.cinematic.tuto1.0",
    "quest.nations.ch03.feedback.bookbad14": "**\"Resimli Antropoloji, Aperirel 972 - yıl 33, 42 numara\"... ...\"Göz çukurundaki evrenin sırrı\"",
}


TARGET_VARIANT_REPLACEMENTS_BY_KEY = {
    "content.67.661": (("455 Mega", "554 Mega"),),
    "content.67.776": (("722-74515212083-C", "722-745152212083-C"),),
    "content.67.777": (("666-754586672071-F", "666-745586672071-F"),),
    "content.67.779": (("42. maddesinde", "42. maddesinin 5. paragrafında"),),
    "content.67.780": (("42. maddesinde", "42. maddesinin 5. paragrafında"),),
    "content.67.834": (("yaklaşık 200 yıl boyunca", "yaklaşık -200 yılında"),),
}


SOURCE_EXACT = {
    "Workshop House \"Pandora's Place\"": "Atölye Evi \"Pandora'nın Mekânı\"",
    "With these Moogrrtrool Boots on, you'll really know how to kick your opponent into shape!":
        "Moogrrtrool Boots'u giydiğinde rakibini hizaya sokmak için tekmeyi nereye atacağını iyi bilirsin!",
    "With these Lifen Sole Boots on, you'll really know how to kick your opponent into shape!":
        "Lifen Sole Boots'u giydiğinde rakibini hizaya sokmak için tekmeyi nereye atacağını iyi bilirsin!",
    "A pendant made from Ethernal Essence, which will stay with you your entire life.":
        "Ömür boyu yanında kalacak Ethernal Essence'tan yapılmış bir kolye.",
    "Always ready for change, these Innovative Boots renew themselves once an eon. Well, almost.":
        "Değişime her zaman hazır olan bu Innovative Boots, çağda bir kendini yeniler. Eh, neredeyse.",
    "If you spot a moving column of smoke from afar, it's probably someone running with their Panache Cloak equipped.":
        "Uzaktan hareket eden bir duman sütunu görürsen muhtemelen Panache Cloak'unu kuşanmış biri koşuyordur.",
    "Crocodyl Leather of very dubious quality. It's probably not worth very much.":
        "Kalitesi son derece kuşkulu Crocodyl Leather. Muhtemelen pek değerli değildir.",
    "Be inapproachable. Rampart Boots.":
        "Ulaşılmaz ol. Rampart Boots.",
    "The Lavamulet gives off plenty of heat, so you'll really appreciate it during those cold winter months. ":
        "The Lavamulet bolca ısı yayar; soğuk kış aylarında değerini gerçekten anlarsın. ",
    "The Warmabones Belt is an original design by Klime the Shoemaker. We all have our own little ways of keeping warm.":
        "Warmabones Belt, Ayakkabıcı Klime'ın özgün tasarımıdır. Hepimizin sıcak kalmak için kendine özgü yöntemleri var.",
    "When life gives you Lemon Jellies, make a Lemon Jelly Amulet!":
        "Hayat sana Lemon Jellies verirse Lemon Jelly Amulet yap!",
    "I have three seconds to tell you that this Canoon Powder is the boooooomb!":
        "Bu Canoon Powder'ın boooooomba olduğunu söylemek için üç saniyem var!",
    "This was actually designed to bear Count Harebourg's Clock Hand, but it turned out to be extremely effective against attacks. ":
        "Aslında Count Harebourg's Clock Hand'i taşımak üzere tasarlanmıştı, ancak saldırılara karşı son derece etkili olduğu ortaya çıktı. ",
    "Hey fellas! Shall I give you the lowdown on the weather? Okay, so today {[1=4]?you'd better dig out your shorts! Sunny all across the region.:}{[3=4]?will be a bit depressing, with lots of clouds.:}{[4=4]?you should get your coat on because there's some good old rain on the way.:}{[5=4]?you can look forward to snowflakes the size of Tofu eggs!:}{[6=4]?you'd do best to stay at home! Rain like a herd of Gobballs relieving themselves!:} Wind fans, {[0=3]?don't be disappointed, but it's going to be dead calm.:}{[1=3]?a nice little breeze should be coming through.:}{[2=3]?it's your lucky day! Howling winds guaranteed!:} Temperatures should be between [#1]° and [#2]°. See you later!":
        "Hey millet! Hava durumunu anlatayım mı? Pekâlâ, bugün {[1=4]?şortları çıkarsanız iyi olur! Bölgenin tamamı güneşli.:}{[3=4]?bol bulutlu, biraz kasvetli olacak.:}{[4=4]?eski usul sağlam bir yağmur geliyor; paltolarınızı giyin.:}{[5=4]?Tofu yumurtası büyüklüğünde kar taneleri bekleyebilirsiniz!:}{[6=4]?evde kalsanız iyi olur! Bir Gobball sürüsü rahatlıyormuş gibi yağmur yağacak!:} Rüzgâr meraklıları, {[0=3]?hayal kırıklığına uğramayın ama hava tamamen durgun olacak.:}{[1=3]?hoş bir meltem esecek.:}{[2=3]?şanslı gününüzdesiniz! Uluyan rüzgârlar garanti!:} Sıcaklık [#1]° ile [#2]° arasında olacak. Görüşürüz!",
    "{[1=1]?Wow! That sun sure is bright! And hot too, isn't it! I wouldn't mind doing a little bit of sunbathing...:}{[3=1]?Boo, enough of this depressing gray. Let's hope it clears up soon!:}{[4=1]?Gr, I hate the rain. It's totally...wet.:}{[5=1]?Cool! Snow! We'll need to have a snowball fight one of these days.:}{[6=1]?What's with this weather?! I'll need to put on my galoshes if this rain doesn't let up!:}":
        "{[1=1]?Vay canına! Güneş ne kadar parlak! Üstelik çok sıcak, değil mi? Biraz güneşlenmek fena olmaz...:}{[3=1]?Off, yeter bu kasvetli grilik. Umarım hava yakında açar!:}{[4=1]?Grr, yağmurdan nefret ediyorum. Her yer... sırılsıklam.:}{[5=1]?Harika! Kar! Bir ara kartopu savaşı yapmalıyız.:}{[6=1]?Bu nasıl hava?! Yağmur dinmezse çizmelerimi giymem gerekecek!:}",
    "Let the Rotceres do their thing. Once they've finished, you'll be the first to know.":
        "Rotcere'leri işlerine bırak. Bitirdiklerinde ilk senin haberin olur.",
    "Let's hope the Ancestral Treechnid's bark is stronger than his bite.":
        "Ancestral Treechnid'in kabuğunun ısırığından daha güçlü olduğunu umalım.",
    "You shall not pass!!": "Geçemezsin!!",
    "A gift from Father Kwismas for writing him a letter!":
        "Father Kwismas'a mektup yazdığın için verdiği bir hediye!",
    "Even the Mamagmote's internal organs are protected by a rocky exoskeleton, like this heart valve.":
        "Mamagmote'un iç organları bile bu kalp kapakçığı gibi kayalık bir dış iskeletle korunur.",
    "It would seem that Black Wabbit Paws bring luck. But Black Wabbits don't carry them; they see lucky charms as a sign of weakness.":
        "Black Wabbit Paws'ın şans getirdiği söylenir. Ancak Black Wabbit'ler onları taşımaz; uğurlu tılsımları zayıflık işareti sayarlar.",
    "They say that Kanniballs have eyes in the back of their heads. You'll understand why when you see this cape!":
        "Kanniball'ların enselerinde gözleri olduğu söylenir. Bu pelerini görünce nedenini anlayacaksın!",
    "It might crush your skull, but you got it from the Schneks - what did you expect?":
        "Kafatasını ezebilir ama onu Schnek'lerden aldın; ne bekliyordun?",
    "This is a practical pair of boots for meowandering through time.":
        "Bu çizmeler zamanda miyavlayarak dolaşmak için oldukça kullanışlıdır.",
    "Ereboria's western beach is under siege by pirates looking for Cire Momore's treasure. They've even managed to get their hands on Foggernaut weapons technology to drastically improve their effectiveness in battle.\\nAmid the pirate crew's attacks, a young boy named Nao seems to have infiltrated their ranks. You don't know how he wound up in this situation, but Nao could be an invaluable source of information, so you'll need to make him your ally.":
        "Ereboria'nın batı sahili, Cire Momore'un hazinesini arayan korsanların kuşatması altında. Korsanlar, dövüşteki etkinliklerini büyük ölçüde artırmak için Foggernaut silah teknolojisini bile ele geçirmiş.\\nKorsan tayfasının saldırıları sırasında Nao adlı genç bir çocuk onların arasına sızmış görünüyor. Bu duruma nasıl düştüğünü bilmiyorsun ancak Nao paha biçilmez bir bilgi kaynağı olabilir; bu yüzden onu müttefikin yapmalısın.",
    "You are Stabilized and can only move by using MP.":
        "Sabitlenmiş durumdasın ve yalnızca MP kullanarak hareket edebilirsin.",
    "They say the Arachnee Embroiderer who strung this bow had to start from scratch 59 times before the Ancestral Treechnid was satisfied with it.":
        "Bu yayı geren Arachnee Embroiderer'ın, Ancestral Treechnid memnun kalana kadar 59 kez baştan başladığı söylenir.",
    "Everyone after the wimp!!": "Herkes pısırığın peşine!!",
    "Curse you!!": "Lanet olsun sana!!",
    "No, this isn't black panther hair decorating this ring, but Badgerox hair.":
        "Hayır, bu yüzüğü süsleyen siyah panter tüyü değil, Badgerox tüyü.",
    "Speak to the Bwork Cook": "Bwork Cook ile konuş",
    "Who hasn't dreamed of having a Wodent ring on their finger?":
        "Kim parmağında bir Wodent yüzüğü olmasını hayal etmemiştir ki?",
    "Amakna has the best dishes!!": "En iyi yemekler Amakna'dadır!!",
    "My name's Donalangelo, I'm in charge around here.":
        "Benim adım Donalangelo; buradan ben sorumluyum.",
    "Bonta has the best planks of wood!!": "En iyi tahta kalaslar Bonta'dadır!!",
    "Apparently Captain Amakna trained here!":
        "Görünüşe göre Captain Amakna burada eğitim almış!",
    "My sword, I want my sword!!": "Kılıcım! Kılıcımı istiyorum!!",
    "I'm Mammy Pal, and this is my Gemlin, Dot!":
        "Ben Mammy Pal, bu da Gemlin'im Dot!",
    "[#1]% at max HP": "Azami Can Puanında [#1]%",
    "50% Damage inflicted in melee": "%50 yakın dövüşte verilen Hasar",
    "Solo: Crackrock Mania": "Bireysel: Crackrock Çılgınlığı",
    "Solo: Ratou Mania": "Bireysel: Ratou Çılgınlığı",
    "Solo: Magmania": "Bireysel: Magma Çılgınlığı",
    "Competitive: Return of the Larvae": "Rekabetçi: Larvaların Dönüşü",
    "Collaborative: Whispered Crackler Invasion": "İşbirlikçi: Whisperer Crackler İstilası",
    "Race: Toad Mania": "Yarış: Kurbağa Çılgınlığı",
    "Solo: Mushd Mania": "Bireysel: Mushd Çılgınlığı",
    "Solo: Prespic Mania": "Bireysel: Prespic Çılgınlığı",
    "Race: Return of the Larvae": "Yarış: Larvaların Dönüşü",
    "Race: Pile of Ashes": "Yarış: Kül Yığını",
    "Race: Birds' Nests": "Yarış: Kuş Yuvaları",
    "Competitive: Birds' Nests": "Rekabetçi: Kuş Yuvaları",
    "Collaborative: Birds' Nests": "İşbirlikçi: Kuş Yuvaları",
    "Competitive: Pile of Ashes": "Rekabetçi: Kül Yığını",
    "Solo: Lost Doll": "Bireysel: Kayıp Bebek",
    "Solo: Blibli Madness": "Bireysel: Blibli Çılgınlığı",
    "Race: Lost Doll": "Yarış: Kayıp Bebek",
    "Solo: Pile of Ashes": "Bireysel: Kül Yığını",
    "Solo: Magmatic Stalagmite": "Bireysel: Magmatik Dikit",
    "Collaborative: Weed Invasion": "İşbirlikçi: Ot İstilası",
    "Solo: Jet-Ski Molluskies": "Bireysel: Jet-Ski Molluskies",
    "Competitive: The Desolation of Smaud": "Rekabetçi: Smaud'un Çoraklığı",
    "Solo: Demolished Rocks": "Bireysel: Yıkılmış Kayalar",
    "Competitive: Demolished Rocks": "Rekabetçi: Yıkılmış Kayalar",
    "Race: Demolished Rocks": "Yarış: Yıkılmış Kayalar",
    "Collaborative: Fungus-Eating Larvae Invasion": "İşbirlikçi: Mantar Yiyen Larva İstilası",
    "Solo: Mycelium": "Bireysel: Miselyum",
    "Solo: Arachnattack": "Bireysel: Arachne Saldırısı",
    "Solo: Lookalike": "Bireysel: Benzer",
    "Solo: Muvegitant Slime": "Bireysel: Muvegitant Balçığı",
    "Collaborative: Demolished Rocks": "İşbirlikçi: Yıkılmış Kayalar",
    "Solo: Backlash": "Bireysel: Ters Tepme",
    "Solo: Blibli Mania": "Bireysel: Blibli Çılgınlığı",
    "Competitive: The School of Champions": "Rekabetçi: Şampiyonlar Okulu",
    "Race: Kitchen Nightmare": "Yarış: Mutfak Kabusu",
    "Solo: Kitchen Nightmare": "Bireysel: Mutfak Kabusu",
    "Competitive: Kitchen Nightmare": "Rekabetçi: Mutfak Kabusu",
    "Competitive: The Call of Koutoulou": "Rekabetçi: Koutoulou'nun Çağrısı",
    "Collaborative: Kitchen Nightmare": "İşbirlikçi: Mutfak Kabusu",
    "Solo: Ohwindy": "Bireysel: Ohwindy",
    "Competitive: Seed of Chunky": "Rekabetçi: Chunky'nin Tohumu",
    "Race: The Leaves of Others": "Yarış: Başkalarının Yaprakları",
    "Competitive: Field Purge": "Rekabetçi: Tarla Arınması",
    "Competitive: Night of the Boowolves": "Rekabetçi: Boowolf'ların Gecesi",
    "Race: Field Purge": "Yarış: Tarla Arınması",
    "Race: Clogged Cog": "Yarış: Tıkanmış Dişli",
    "Solo: Fungus Pocus": "Bireysel: Fungus Pocus",
    "Race: Sudden Distortion": "Yarış: Ani Bozulma",
    "Collaborative: Sudden Distortion": "İşbirlikçi: Ani Bozulma",
    "Competitive: Sudden Distortion": "Rekabetçi: Ani Bozulma",
    "Solo: Night of the Boowolves": "Bireysel: Boowolf'ların Gecesi",
    "Solo: Deformed Crackmite": "Bireysel: Biçimsiz Crackmite",
    "Race: Top of the Lollipops": "Yarış: Lolipopların Zirvesi",
    "Competitive: White Canine": "Rekabetçi: Beyaz Köpek",
    "Race: Crystal Droplets": "Yarış: Kristal Damlacıklar",
    "Solo: Molluscapade": "Bireysel: Molluscapade",
    "Solo: Granite Terror": "Bireysel: Granit Dehşeti",
    "Race: Granite Terror": "Yarış: Granit Dehşeti",
    "Collaborative: Krakottes on the Run": "İşbirlikçi: Kaçan Krakotte'lar",
    "Race: Glacial Digestion": "Yarış: Buzul Sindirimi",
    "Competitive: Krakottes on the Run": "Rekabetçi: Kaçan Krakotte'lar",
    # Critical model artifacts and foreign-script contamination.
    "After leaving Olavran's lair, you went to see Otomai, who showed you how to leave Incarnam. And although you couldn't use the Zaap as expected, you succeeded in getting to Astrub, in the World of Twelve. You are newly and officially incarnated as a Twelvian.\\nNext stop: adventure!":
        "Olavran'ın ininden ayrıldıktan sonra, Incarnam'dan nasıl çıkacağını gösteren Otomai'yi ziyaret ettin. Zaap'ı beklendiği gibi kullanamamış olsan da On İkiler Dünyası'ndaki Astrub'a ulaşmayı başardın. Artık resmen bedenlenmiş yeni bir On İkili'sin.\\nSıradaki durak: macera!",
    "Freezepop - the coolest ice confection around, from Missiz Freezz!\\nIt'll wake the dead!\\nA Freezepop in the morning to dispel De Darm and all those nasty effects associated with death!":
        "Freezepop, Missiz Freezz'in en havalı buzlu şekeridir!\\nÖlüleri bile uyandırır!\\nSabah bir Freezepop yiyerek De Darm'ı ve ölümle ilişkili tüm o kötü etkileri dağıt!",
    "I don't know who your thief is, but I recognize a certain smell. Not the strongest in the world, but it's the smell of an Ecaflip who lives in the Tailors' Quarter of Astrub. In fact, she's the one in charge of it! If you want my opinion, that's the start of a solid lead. Good luck!":
        "Hırsızının kim olduğunu bilmiyorum ama tanıdık bir koku alıyorum. Çok güçlü değil; Astrub'daki Tailors' Quarter bölgesinde yaşayan bir Ecaflip'in kokusu. Hatta oradan o sorumlu! Bana sorarsan sağlam bir ipucu buldun. Bol şans!",
    "Bilbizan Taroudium Quarry": "Bilbizan Taroudium Ocağı",
    "Bilbizan Sandy Ore Quarry": "Bilbizan Sandy Ore Ocağı",
    "Bilbizan Mythwil Quarry": "Bilbizan Mythwil Ocağı",
    "This fight lasts <text color=\"importantTextColor\">13 turns.</text> It is won as soon as 13 turns have passed, or lost when Karn dies.\\n\\nThe goal is to survive and inflict as much damage as possible on the boss.":
        "Bu dövüş <text color=\"importantTextColor\">13 tur sürer.</text> 13 tur dolduğu anda kazanılır; Karn ölürse kaybedilir.\\n\\nAmaç hayatta kalmak ve boss'a olabildiğince fazla hasar vermektir.",
    "[el3] spells steal 120% of [el3] damage inflicted. When under the effects of this connection, total Armor cannot exceed 40% of the Iop's max HP.":
        "[el3] büyüleri, verilen [el3] hasarının %120'si kadar Can çalar. Bu bağlantının etkisi altındayken toplam Zırh, Iop'un azami Canının %40'ını aşamaz.",
    "Monsters gain bonuses for each active Stasis Crystal:\\n[pl]100 Elemental Resistance\\n[pl]20% damage inflicted\\n\\nPlayers who start their turn adjacent to an active crystal gain bonuses:\\n[pl]100 Elemental Resistance (1 turn, stackable)\\n[pl]20% damage inflicted (1 turn, stackable)\\n\\nAt end of turn, if at least one Stasis Crystal is deactivated:\\n[pl]Reactivates a Stasis Crystal":
        "Canavarlar, etkin her Stasis Crystal için bonus kazanır:\\n[pl]100 Element Direnci\\n[pl]%20 Verilen Hasar\\n\\nTuruna etkin bir Stasis Crystal'ın bitişiğinde başlayan oyuncular şunları kazanır:\\n[pl]100 Element Direnci (1 tur, birikir)\\n[pl]%20 Verilen Hasar (1 tur, birikir)\\n\\nTur sonunda en az bir Stasis Crystal devre dışıysa:\\n[pl]Bir Stasis Crystal'ı yeniden etkinleştirir",
    "The Sacrier transfers some of their health to an ally and then switches places with them. If they target themself, some of their Armor is converted to healing.":
        "Sacrier Canının bir bölümünü bir müttefiğe aktarır, ardından onunla yer değiştirir. Kendini hedeflerse Zırhının bir bölümü iyileştirmeye dönüşür.",
    "\\n<b>17th Junssidor 549</b>\\nI'm obsessed by this theory. I'm going to try a few experiments, basing them on the list of ingredients I've managed to compile. If I add other resources, I might end up figuring out the recipe! We'll see... I've already ordered a big piece of Dark Treechnid Bark. I hope it will work! I'm really going into this blind, but nothing ventured, nothing gained!":
        "\\n<b>17 Junssidor 549</b>\\nBu teoriye kafayı taktım. Derlemeyi başardığım malzeme listesini temel alarak birkaç deney yapacağım. Başka kaynaklar eklersem sonunda tarifi çözebilirim! Göreceğiz... Büyük bir parça Dark Treechnid Bark sipariş ettim bile. Umarım işe yarar! Tamamen el yordamıyla ilerliyorum ama risk almadan kazanç olmaz!",
    "\\nDay 62 - 6 days sailing through the frozen and foggy waters - still nothing. Why did I take this job again? What an idea!\\n[...]\\nDay 65 - We've just met another ship. A very old and damaged model. What with the fog, we almost collided! The strangest thing was it seemed completely deserted, not a living soul could be seen on board. We didn't dare board it, for fear of not being able to get back to our ship afterwards.\\n\\nDay 67 - My navigator has finally understood why we couldn't find our way out of the fog. It would seem that in this particular region, the winds and currents all travel in the same direction, rotating around a central point. We've been going round in circles for almost two weeks!\\nUsing an clever system of buoys tied together, we were able to determine which way to turn to head towards the center of the ring of current.":
        "\\n62. Gün - Donmuş ve sisli sularda 6 gündür seyrediyoruz; hâlâ hiçbir şey yok. Bu işi neden kabul ettim? Ne fikirmiş!\\n[...]\\n65. Gün - Az önce başka bir gemiyle karşılaştık. Çok eski ve hasarlı bir modeldi. Sis yüzünden neredeyse çarpışıyorduk! En tuhafı, geminin tamamen terk edilmiş görünmesiydi; güvertede tek bir canlı bile yoktu. Sonra kendi gemimize dönememekten korktuğumuz için gemiye çıkmaya cesaret edemedik.\\n\\n67. Gün - Seyrüsefercim sonunda sisten neden çıkamadığımızı anladı. Görünüşe göre bu bölgede rüzgârlar ve akıntılar aynı yönde, merkezi bir noktanın çevresinde dönüyor. Yaklaşık iki haftadır daire çiziyormuşuz!\\nBirbirine bağlanmış şamandıralardan oluşan akıllıca bir sistemle, akıntı halkasının merkezine ulaşmak için hangi yöne dönmemiz gerektiğini belirledik.",
    "He used the Branchy-Flower! Oh, what a brilliant idea. Trust me when I say I'm proud, because it's me who taught him everything! He was one hell of a kid when he arrived, but I turned him in to one of our best Huppermages. Since then, his feats have been stacking up. I still remember the day I was told how he managed to beat his opponents in hand-to-hand combat during a terrible fight. He has a bleeding heart for the oppressed. After having started with quietly doing in a few Snow Boohemoths, he was pinned to the ground by a shock which terrified his two helpless spectators. With the two miraculously cured spectators watching, a look of despair in their eyes, uncertain of what was going to happen, my champion got straight back up, with all his muscles flexing. A call to violence, deep down within him, reverberated like a strange euphoric symphony. He immersed himself in it up to his eyeballs, awaking the enthusiasm of a fighter in him, who is sure to fight for a just cause. Secluded in his inner tower, surrounded by an isle of light, the ground seemed to open up beneath his feet as he felled the woefully famous Yech'Ti. In short, an astounding person... Why did you come here again?":
        "Branchy-Flower'ı kullandı! Ne parlak bir fikir. Gurur duyduğumu söylediğimde bana inan; ona bildiği her şeyi ben öğrettim! Buraya geldiğinde tam bir baş belasıydı ama onu en iyi Huppermage'larımızdan birine dönüştürdüm. O günden beri başarılarının ardı arkası kesilmiyor. Korkunç bir dövüşte rakiplerini göğüs göğüse yenmeyi nasıl başardığını anlattıkları günü hâlâ hatırlıyorum. Ezilenlere karşı yufka yüreklidir. Birkaç Snow Boohemoth'u sessizce alt ettikten sonra, iki çaresiz seyirciyi dehşete düşüren bir darbeyle yere çakılmış. Mucize eseri iyileşen iki seyirci, ne olacağını bilemeden umutsuzluk içinde bakarken şampiyonum bütün kasları gerilmiş hâlde hemen ayağa kalkmış. İçindeki şiddet çağrısı, tuhaf ve coşkulu bir senfoni gibi yankılanmış. Kendini bütünüyle bu sese bırakıp haklı bir dava uğruna savaşacak dövüşçünün tutkusunu uyandırmış. İç kulesine çekilmiş, bir ışık adasıyla çevrelenmişken, hazin şöhretli Yech'Ti'yi yere serdiğinde ayaklarının altındaki zemin yarılmış gibi görünmüş. Kısacası olağanüstü biri... Sen buraya neden gelmiştin?",
    "What scandal was caused by the review Anthropology Illustrated - year 33 no. 42?":
        "Anthropology Illustrated dergisinin 33. yıl 42. sayısındaki inceleme hangi skandala yol açtı?",
    "*The light returns, and the feeling of weakness leaves you*\\n\\nConvinced that Lady Jhessica was behind the drought affecting Ohwymi Island, Tal Kasha and her men assassinated Lady Jhessica. Xelor was furious with her, however. He broke the hourglass and cursed Tal Kasha and her assassins, condemning them to an eternity of undeath.\\n\\nThey could never leave the cursed pyramid or rest in peace ever again.":
        "*Işık geri döner ve üzerindeki güçsüzlük hissi kaybolur*\\n\\nTal Kasha ve adamları, Ohwymi Adası'nı etkileyen kuraklığın arkasında Lady Jhessica'nın olduğuna inanıp onu öldürdüler. Ancak Xelor buna öfkelendi. Kum saatini kırdı; Tal Kasha ile suikastçılarını lanetleyerek onları sonsuza dek yaşayan ölüler olmaya mahkûm etti.\\n\\nArtık lanetli piramitten asla ayrılamayacak, huzur içinde yatamayacaklardı.",
    "It's a substance with many wisks and benefits. Its appeawance is that of a wed powdew with yellow flecks... The puwest kind can be found in the pywamid of Tal Kasha.\\n\\n*He softly taps the page of the report*\\n\\nYes, the cowpowation in Ohwymi had held talks with the Wabbit scientists back then. Let's see... Yes, of couwse.":
        "Pek çok riski ve faydası olan bir madde. Sarı benekli kırmızı bir toz görünümünde... En saf türü Tal Kasha'nın piramidinde bulunur.\\n\\n*Raporun sayfasına hafifçe vurur*\\n\\nEvet, Ohwymi'deki şirket o zamanlar Wabbit bilim insanlarıyla görüşmüş. Bakalım... Evet, elbette.",
    "Well, yes... I discovered a stele not far from here, in Cania. It describes the birth of Crocoburio, the son of Grougalorasalar, a great crocodyl warrior who terrorized Bonta.\\n\\nIt's a story that dates back many centuries. It's always thrilling to try and figure out what's truth and what's fiction!":
        "Şey, evet... Buradan çok uzakta olmayan Cania'da bir dikilitaş keşfettim. Bonta'ya dehşet saçan büyük timsah savaşçı Grougalorasalar'ın oğlu Crocoburio'nun doğumunu anlatıyor.\\n\\nBu hikâye yüzyıllar öncesine dayanıyor. Neyin gerçek, neyin kurgu olduğunu çözmeye çalışmak her zaman heyecan verici!",
    "Amber Stele": "Amber Dikilitaşı",

    # Referenced original item/skill names and malformed descriptions.
    "The Ally Baba Turban will topple you over! It's so large that you can fit 40 Bow Meows underneath!":
        "Ally Baba Turban seni devirebilir! O kadar büyük ki altına 40 Bow Meow sığdırabilirsin!",
    "This costume represents Silouate, wise Minotoror and Protector of Aperirel.":
        "Bu kostüm, bilge Minotoror ve Aperirel'in Koruyucusu Silouate'ı temsil eder.",
    "Thankfully, Cawwots awe still pwesent in the Wowld of Twelve. You wouldn't have it any othew way.":
        "Cawwot'ların hâlâ On İkiler Dünyası'nda bulunmasına şükür. Başka türlüsünü istemezdin.",
    "The Amulet of Howlieng Wind produces impressive energy in the presence of ambient winds and vapors. It is said that the power of its rotation is so strong that a curious Puddly could end up being scattered to the four corners of the World of Twelve if it came too close.":
        "Amulet of Howlieng Wind, çevredeki rüzgâr ve buharların etkisiyle olağanüstü miktarda enerji üretir. Dönüş gücünün o kadar yüksek olduğu söylenir ki meraklı bir Puddly fazla yaklaşırsa On İkiler Dünyası'nın dört bir yanına savrulabilir.",
    "This blueprint will teach you the recipe for the item \"Travel Cloak\" for the Tailor profession.":
        "Bu taslak, Terzi mesleğinde Travel Cloak eşyasının tarifini öğretir.",

    # Buff/effect grammar and English residue.
    "TEST DEATH NEMOTILUS ALLY": "TEST ÖLÜM NEMOTILUS MÜTTEFİK",
    "is reborn from the ashes (Allies still present)": "küllerinden yeniden doğar (Müttefikler hâlâ mevcut)",
    "The Coat of Granite cracks": "Coat of Granite çatlar",
    "The Coat of Rock cracks": "Coat of Rock çatlar",
    "[se] (Vow of Silence)": "[se] (Sessizlik Yemini)",
    "test 1 - feedback chat + caster": "test 1 - geri bildirim sohbeti + kullanan",
    "[se] (Prison of Darkness)": "[se] (Karanlık Hapishanesi)",
    "lost the obligation of the Vow of Silence for 2 turns!": "Sessizlik Yemini yükümlülüğünü 2 tur boyunca kaybeder!",
    "[se] (Heart of Light)": "[se] (Heart of Light)",
    "[se] (Heart of Light active)": "[se] (Heart of Light etkin)",
    "[se] (Back to Back)": "[se] (Sırt Sırta)",
    "Damage is reflected (Back to Back)": "Hasar yansıtılır (Sırt Sırta)",
    "Invulnerable (Sewum)": "Bağışık (Sewum)",
    "Invulnerable (Conductor)": "Bağışık (Kondüktör)",
    "applies the Invulnerable state": "Bağışık durumunu uygular",
    "Invulnerable when the attacker is not in line with Flaxhid": "Saldırgan Flaxhid ile aynı hizada değilse bağışık olur",
    "Invulnerable:\\n[pl]It's not time before time, and after time the time has past": "Bağışık:\\n[pl]Vakti gelmeden olmaz; vakti geçince de çok geç olur",
    "Krosmoprotection: Immune to damage\\nRift identified: golem's back": "Krosmoprotection: Hasara karşı bağışık\\nYarık belirlendi: golemin arkası",
    "Krosmoprotection: Immune to damage\\nRift identified: golem's sides": "Krosmoprotection: Hasara karşı bağışık\\nYarık belirlendi: golemin yanları",
    "Krosmoprotection: Immune to damage\\nRift identified: golem's front": "Krosmoprotection: Hasara karşı bağışık\\nYarık belirlendi: golemin önü",
    "Krosmoprotection: Immune to damage\\nRift not identified": "Krosmoprotection: Hasara karşı bağışık\\nYarık belirlenemedi",
    "Immune to damage": "Hasara karşı bağışık",
    "Invulnerable to fire": "Ateş hasarına karşı bağışık",
    "Invulnerable to water": "Su hasarına karşı bağışık",
    "Invulnerable to earth": "Toprak hasarına karşı bağışık",
    "Invulnerable to Damage inflicted at a distance": "Menzilden verilen hasara karşı bağışık",
    "On Sydonia's next turn:\\nApplies [se] if the player isn't [st4350]\\nOR": "Sydonia'nın sonraki turunda:\\n[se] uygular; oyuncuda [st4350] yoksa\\nVEYA",
    "Invulnerable to damage when the bearer is not near a rock": "Taşıyıcı bir kayanın yakınında değilken hasara karşı bağışık",
    "Requires having cast Go\\nCast on a Double:\\n[pl][se]\\n[pl][caster] can once again use all their spells": "Önceden Go kullanılmış olmalıdır\\nBir Double üzerinde kullanıldığında:\\n[pl][se]\\n[pl][caster] tüm büyülerini yeniden kullanabilir",
    "Not enough shadow zones on the field; shadows protect Shadofang:\\n[pl]Immune to damage": "Sahada yeterli gölge alanı yok; gölgeler Shadofang'ı korur:\\n[pl]Hasara karşı bağışık",
    "[caster] swaps second current mastery for Air Mastery": "[caster] ikinci mevcut ustalığını Hava Ustalığıyla değiştirir",
    "When the boss is attacked from behind, the boss calls for reinforcements!\\nWhat's the secret behind this hocus-pocus?\\nInvulnerable as long as there are not 3 or more other hats": "Boss arkadan saldırıya uğradığında takviye çağırır!\\nBu hokus pokusun sırrı ne?\\nEn az 3 başka şapka bulunmadığı sürece bağışık",
    "Immune to damage from more than 3 cells away.\\nWhen destroyed, the attacker gains [$1$1ef]": "3 hücreden daha uzaktan gelen hasara karşı bağışık.\\nYok edildiğinde saldırgan [$1$1ef] kazanır",
    "Invulnerable to damage": "Hasara karşı bağışık",
    "[#1]% Damage Inflicted on the Challenge monsters": "Meydan okuma canavarlarına verilen hasar: [#1]%",
    "\\nFor now: Invulnerable": "\\nŞimdilik: Bağışık",
    "Air Damage": "Hava Hasarı",
    "The state bearer gains 200 Resistance and 30% Damage Inflicted if they were not in the Chain of Destiny": "Durum taşıyıcısı Kader Zinciri'nde değilse 200 Direnç ve %30 Verilen Hasar kazanır",
    "The state bearer has been touched by the Chain of Destiny": "Kader Zinciri durum taşıyıcısına dokundu",
    "Disperses Wafts of Orvalus Root Beer": "Orvalus Kök Birası Esintilerini dağıtır",
    "Allies:\\n[pl][st3434]\\n\\nEnemies:\\n[pl]-30% damage inflicted in melee": "Müttefikler:\\n[pl][st3434]\\n\\nDüşmanlar:\\n[pl]Yakın dövüşte -%30 Verilen Hasar",
    "Invulnerable to melee damage": "Yakın dövüş hasarına karşı bağışık",
    "Immune to damage\\nSkips turn\\nThe Guawd no longer serves the Wa": "Hasara karşı bağışık\\nTurunu atlar\\nGuawd artık Wa'ya hizmet etmez",
    "\\nState is lost if the [caster] loses their Armor": "\\n[caster] Zırhını kaybederse durum sona erer",
    "Invulnerable to damage\\nCannot be KO'd": "Hasara karşı bağışık\\nNakavt edilemez",
    "15% ranged damage inflicted\\nImmune to the [st8986] state": "%15 Menzilli Verilen Hasar\\n[st8986] durumuna karşı bağışık",
    "Gives the Ally Baba Set": "Ally Baba Set verir",
    "Aura of Support [CIRCLE] (of 3)\\nAura of Healing [CIRCLE] (of 3)": "Destek Aurası [CIRCLE] (3 hücre)\\nİyileştirme Aurası [CIRCLE] (3 hücre)",
    "Fire Note": "Ateş Notası",
    "Earth Note": "Toprak Notası",
    "Water Note": "Su Notası",
    "Immune to damage when under the influence of a Moon": "Bir Moon'un etkisi altındayken hasara karşı bağışık",
    "Resistance to death": "Ölüme karşı direnç",
    "Immune to damage when the attacker is more than 3 cells from the Mini-Lenald": "Saldırgan Mini-Lenald'dan 3 hücreden daha uzaktaysa hasara karşı bağışık",
    "Consumes Elemental Disciple": "Elemental Disciple tüketir",
    "+1 MP (Dog Handler)": "+1 MP (Dog Handler)",
    "-1 MP (Arachnee Silk)": "-1 MP (Arachnee Silk)",
    "Loses one level of Sneaky Shield": "1 seviye Sneaky Shield kaybeder",
    "Abundance is limited to 60 levels (Elemental Combination)": "Abundance 60 seviyeyle sınırlıdır (Elemental Combination)",
    "Lucky Seven: [#1] card{[>1]?s:}": "Lucky Seven: [#1] kart{[>1]?s:}",
    "-1 AP (Treechnid Sap)": "-1 AP (Treechnid Sap)",

    # Quoted/referenced skill and item names stay exactly as shipped by WAKFU.
    "Use a \"Characteristics Reset\" to reset this Characteristics page.":
        "Bu Özellikler sayfasını sıfırlamak için Characteristics Reset kullan.",
    "Xunil the Megalomaniac wanted to become the best Xelor in the World. People made fun of him so much that he ended up making this \"Master of Time Belt\" so people would take him more seriously.":
        "Megalomanyak Xunil dünyanın en iyi Xelor'u olmak istiyordu. İnsanlar onunla öylesine alay etti ki kendisini daha ciddiye almaları için Master of Time Belt'i yaptı.",
    "This is the \"Shovel Shaker\" spell, borrowed from the Enutrof class. The Huppermage inflicts damage on enemies in front of them and removes MP from them. They gain a Force of Will bonus for the duration of the spell, based on the number of runes they have.":
        "Bu, Enutrof sınıfından ödünç alınan Shovel Shaker büyüsüdür. Huppermage önündeki düşmanlara hasar verir ve MP'lerini azaltır. Sahip olduğu rün sayısına bağlı olarak büyü süresince İrade bonusu kazanır.",
    "At start of turn, the Rogue accumulates the \"Rogue Master\" state up to a maximum level of 5. Upon switching from Sneaky to Runaway, or from Runaway to Sneaky, the Rogue will gain additional bonuses depending on the mode. In exchange, the Ruse spell has a 2 turn cooldown.":
        "Tur başında Rogue, en fazla 5 seviyeye ulaşabilen Rogue Master durumunu biriktirir. Sneaky modundan Runaway moduna ya da Runaway modundan Sneaky moduna geçtiğinde, moda bağlı olarak ek bonuslar kazanır. Bunun karşılığında Ruse büyüsünün bekleme süresi 2 tur olur.",
    "Go to the Xelorium and complete the quest \"Déjà Vu\" to recover the \"Xelor's Sandglass\" Artifact.":
        "Xelorium'a git ve Xelor's Sandglass eserini geri almak için \"Déjà Vu\" görevini tamamla.",
    "Speak to Kali on the Upper Slope of Zinit after getting the \"Darkli Moon Hammer\" from Darkli Moon.":
        "Darkli Moon'dan Darkli Moon Hammer'ı aldıktan sonra Zinit'teki Üst Yamaç bölgesinde Kali ile konuş.",
    "This scroll will teach you the \"Summon a Pet\" emote.":
        "Bu tomar, Evcil Hayvan Çağır ifadesini öğretir.",
    "This blueprint will teach you the recipe for the \"Monbow Tree\" item for the Lumberjack profession.":
        "Bu taslak, Oduncu mesleği için Monbow Tree eşyasının tarifini öğretir.",
    "Hmmm... I think it's called the \"Rikiki Wand\"!\\nIf my memory serves me right, it can be found on Monk Island, in a secret room in the Undieworld Dungeon.":
        "Hımm... Sanırım adı Rikiki Wand!\\nYanlış hatırlamıyorsam Monk Island'da, Undieworld Dungeon içindeki gizli bir odada bulunabilir.",
    "The Xelor Dimension? Heh, no... Why, is it important? Travel through time with the \"Xelor's Sandglass\" artifact, you say? Ok, ok, I'll go look for it then...":
        "Xelor Boyutu mu? Heh, hayır... Neden, önemli mi? Xelor's Sandglass eseriyle zamanda yolculuk mu? Tamam, tamam; gidip onu arayayım...",
    "Wake up Milkar (requires the \"Full Moon\" key) ":
        "Milkar'ı uyandır (Full Moon anahtarı gerekir) ",
    "** \"Spherolithic Encyclopedia\"... ...\"Radius, circumference and sinusoidality\"...":
        "** \"Spherolithic Encyclopedia\"... ...\"Yarıçap, çevre ve sinüzoidalite\"...",
    "Don't worry, this breastplate only provokes constant worrying in 74.999% of cases. Go ahead - put it on.":
        "Endişelenmeyin; bu göğüslük vakaların yalnızca %74,999'unda sürekli kaygıya yol açar. Haydi, giyin.",
    "This belt seems to have come straight from another time. It was seemingly left by a mad scientist who could often be heard gibbering scientific jargon that made no sense like, \"2.21 gigowatts?! 2.21 gigowatts... How could I have been so careless?!\"":
        "Bu kemer doğrudan başka bir zamandan gelmiş gibi. Görünüşe göre, \"2,21 gigowatt mı?! 2,21 gigowatt... Nasıl bu kadar dikkatsiz olabildim?!\" gibi anlamsız bilimsel sözler mırıldanan çılgın bir bilim insanı tarafından bırakılmış.",
}


ITEM_DESCRIPTION_EXACT = {
    "A Saddle and Reins for a dragoturkey":
        "Bir dragoturkey için Saddle and Reins",
    "A beautiful dresser made of noble Cherry Tree Wood.":
        "Soylu Cherry Tree Wood kullanılarak yapılmış güzel bir şifonyer.",
    "A journal found on the skeleton of a Sadida Guard. Some of the pages have been chewed on by a Moowolf.":
        "Bir Sadida Muhafızının iskeletinde bulunan günlük. Sayfaların bazılarını bir Moowolf kemirmiş.",
    "A real Golden Bow Meow, because you're worth it!":
        "Gerçek bir Golden Bow Meow; çünkü buna değersin!",
    "A reward for the winners of the Miss and Mister May contest.":
        "Miss and Mister May yarışmasının kazananlarına verilen ödül.",
    "A variant of the very specialized version originating from the Monkey King, these Moon Epaulettes are no less effective.":
        "Monkey King'den gelen son derece özel sürümün bir çeşidi olan bu Moon Epaulettes de en az onun kadar etkilidir.",
    "After preparing this great Tofire Skin, you'll be nothing but skin and bone!":
        "Bu iri Tofire Skin'i hazırladıktan sonra bir deri bir kemik kalacaksın!",
    "Albatrocious Feather trade is a big hit in Brakmar. Its inhabitants use it to torture Bontarians...":
        "Albatrocious Feather ticareti Brakmar'da çok tutuluyor. Bölge halkı bu tüyleri Bontalılara işkence etmek için kullanıyor...",
    "Ash Wood has proven anti-aging properties. You just have to be able to put up with the diuretic effects.":
        "Ash Wood'un yaşlanma karşıtı özellikleri kanıtlanmıştır. Yalnızca idrar söktürücü etkisine katlanabilmen gerekir.",
    "Be careful: this All Mushray makes a mess everywhere it goes.":
        "Dikkatli ol: Bu All Mushray gittiği her yeri birbirine katar.",
    "Big boom? Yeah, big boom! Big Bad Aboum boom! ":
        "Büyük patlama mı? Evet, büyük patlama! Kocaman bir Bad Aboum patlaması! ",
    "Copper Ore gets its color from its excellent thermal conductivity. Perfect for taking your temperature when you're in the company of an attractive adventurer. ":
        "Copper Ore rengini mükemmel ısı iletkenliğinden alır. Çekici bir maceracının yanındayken ateşini ölçmek için birebirdir. ",
    "Elderberry Wood contains a concentrated poison deep in its bark.":
        "Elderberry Wood'un kabuğunun derinliklerinde yoğun bir zehir bulunur.",
    "Gone with the wind.\\nUse this figurine to add it to your Krosmaster collection.":
        "Rüzgâr gibi geçti.\\nBu figürünü Krosmaster koleksiyonuna eklemek için kullan.",
    "Hallowed Pooplar Wood is fairly resistant and difficult to split.":
        "Hallowed Pooplar Wood oldukça dayanıklıdır ve yarılması zordur.",
    "Here you have the revolutionary, first-of-their-kind, waterproof, all-singing, all-dancing Pioneer Boots. With these on, you'll be able to rise above most situations in the World of Twelve.":
        "İşte devrim niteliğinde, türünün ilk örneği, su geçirmez, şarkı söyleyip dans eden Pioneer Boots. Bunları giyince On İkiler Dünyası'ndaki çoğu durumun üstesinden gelebilirsin.",
    "Its meat is juicy, tender, and delicious. But beware: Eating too much Sea Boss can lead to severe stomach aches, especially when it regenerates and comes back to life to chew on your entrails.":
        "Eti sulu, yumuşak ve lezzetlidir. Ama dikkat: Fazla Sea Boss yemek ciddi mide ağrılarına yol açabilir; özellikle de kendini yenileyip bağırsaklarını çiğnemek üzere hayata dönerse.",
    "Leather, teeth and hair: what makes the Trapper Belt great. ":
        "Deri, diş ve kıl: Trapper Belt'i harika yapan her şey. ",
    "Legend has it that if you roam with these boots and you find a Gon Door Hinge, you're crowned king.":
        "Efsaneye göre bu çizmelerle dolaşırken bir Gon Door Hinge bulursan kral ilan edilirsin.",
    "Made from Eternal Ice, these daggers can pierce any material except the Sun itself, or any science class replica of the Sun, or anything remotely warm, like a fresh loaf.":
        "Eternal Ice'tan yapılan bu hançerler; Güneş'in kendisi, fen dersindeki bir Güneş maketi veya taze bir somun ekmek gibi azıcık sıcak olan şeyler dışında her türlü malzemeyi delebilir.",
    "More lively than the wind, the Breath of Life travels through time to cut the lives of the living.":
        "Rüzgârdan bile canlı olan Breath of Life, yaşayanların canını biçmek için zamanda yolculuk eder.",
    "Mortal Wood leaves you with poison on your hands when you handle it.":
        "Mortal Wood'u tuttuğunda ellerinde zehir bırakır.",
    "Now you have The Watch, time is in your hands! You can be as late as you like!":
        "Artık The Watch sende; zaman ellerinde! İstediğin kadar geç kalabilirsin!",
    "Ooh rah, ooh la la! My Cloudy Piwat! - Brrrbley Spears":
        "Oo rah, oo la la! Benim Cloudy Piwat'ım! - Brrrbley Spears",
    "Pooplar Wood is light and bendy.":
        "Pooplar Wood hafif ve esnektir.",
    "Raval's Report to Oropo on the Elemental Towers.":
        "Raval's Report: Element Kuleleri hakkında Oropo'ya sunulan rapor.",
    "Royal Jelly is a secretion from King Jellix's cephalic glands. In short, it's a royal loogie.":
        "Royal Jelly, King Jellix'in başındaki bezlerden salgılanır. Kısacası krallara layık bir balgamdır.",
    "Royal is the aroma of warm sap that seeps from the Natroyal Costume. If you wear it in the middle of the the Treechnid Forest, you'll surely attract all of the Bow Wows taking a stroll!":
        "Natroyal Costume'dan sızan sıcak özsuyun kokusu krallara layıktır. Onu Treechnid Ormanı'nın ortasında giyersen gezintiye çıkmış bütün Bow Wow'ları kesinlikle kendine çekersin!",
    "See-Food Pie a la Sufokia is a traditional dish thrown together out of whatever vaguely edible looking scraps the Sufokians could find to welcome home the fishermen who had been at sea for weeks hunting the Giant Kralove. Nowadays, they make it to celebrate all sorts of special occasions.":
        "See-Food Pie a la Sufokia, Sufokialıların Giant Kralove avında haftalarca denizde kalan balıkçıları karşılamak için yenilebilir görünen ne buldularsa bir araya getirerek hazırladığı geleneksel bir yemektir. Günümüzde her türlü özel günü kutlamak için yapılır.",
    "Sick of having to create your own disorder? What you need is the Pile of Books, which will mask your excessive tidiness of your abode. A must-have!":
        "Kendi dağınıklığını yaratmaktan bıktın mı? Aradığın şey Pile of Books; evindeki aşırı düzeni gizler. Olmazsa olmaz!",
    "Stolen Epaulettes are the sweetest.":
        "En tatlısı Stolen Epaulettes'tir.",
    "Strich Bag? Or Bag of Strich?\\nThat is the question...":
        "Strich Bag mi? Yoksa Bag of Strich mi?\\nİşte bütün mesele bu...",
    "The Cap helps spongy bodies maintain equilibrium and also guards against obscene thoughts.":
        "The Cap, süngersi bedenlerin dengesini korumasına yardım eder ve müstehcen düşüncelere karşı da korur.",
    "The Cuddly Bow Meow Fish is a variety of Bow Meow Fish that loves a good cuddle, hence its name.":
        "Cuddly Bow Meow Fish, sarılmaya bayılan bir Bow Meow Fish çeşididir; adı da buradan gelir.",
    "The Foolmoun weighs about as much as a dead Moogrr, but it's waterproof and resistant to Boowolf scratches. Sometimes, Trools even use it as a mirror.":
        "The Foolmoun yaklaşık ölü bir Moogrr kadar ağırdır; ama su geçirmez ve Boowolf tırmalamalarına dayanıklıdır. Bazen Trool'lar onu ayna olarak bile kullanır.",
    "The Gougnole is made from the moon stone, which had been soaking in a barrel of root beer for 5000 years. As a result, it's awfully powerful.":
        "The Gougnole, 5000 yıl boyunca bir fıçı kök birasında bekletilmiş ay taşından yapılır. Bu yüzden korkunç derecede güçlüdür.",
    "The Goultard was soaked in a Dragon Pig's blood. Any hero who can bear the stench given off by the sword will have earnt the right to use it in battle.":
        "The Goultard, Dragon Pig'in kanına batırılmıştır. Kılıcın yaydığı kokuya dayanabilen her kahraman onu dövüşte kullanma hakkını kazanır.",
    "The Hotty will give you a burning desire to knock out your enemies... as if you didn't want to already!":
        "The Hotty, düşmanlarını yere serme isteğini alevlendirir... Sanki bunu zaten istemiyormuşsun gibi!",
    "The Korko Klako is a beautifo hato worno by the mo handso Sadido.":
        "The Korko Klako, en yakışıklı Sadida'nın taktığı güzel bir şapkadır.",
    "The Overdrawn allows for debts to be settled or damage to be dealt over time.":
        "The Overdrawn, borçların kapatılmasını veya hasarın zamana yayılmasını sağlar.",
    "The legendary Poak Cloak was specially embroidered for warriors who live for close combat situations.":
        "Efsanevi Poak Cloak, yakın dövüş için yaşayan savaşçılara özel olarak işlenmiştir.",
    "There's not Mushd to it and it looks a bit Mushd but there we have it; a Mushd Hand.":
        "Pek Mushd bir yanı yok, biraz da ezilmiş görünüyor ama işte karşınızda: Mushd Hand.",
    "These 200 and some cards are numbered in an unusual order. If you put them in the right order, you'll see that it represented the relationship between the circumference of a circle and its diameter in Euclidian plane - duh.\\nIt's always easier to do 100 Hexotic cards than 100 Eternal Swords, anyway.":
        "Bu iki yüz küsur kart alışılmadık bir sırayla numaralandırılmıştır. Doğru sıraya koyarsan Öklid düzleminde bir dairenin çevresi ile çapı arasındaki oranı gösterdiklerini görürsün; ne kadar şaşırtıcı!\\nNe de olsa 100 Hexotic kart yapmak, 100 Eternal Sword yapmaktan her zaman daha kolaydır.",
    "These Gobbalrog Boots will allow you to give a good boot to any flaming Gobbowl Ball coming your way.":
        "Gobbalrog Boots, sana doğru gelen alevli Gobbowl Ball'a sağlam bir tekme atmanı sağlar.",
    "These may look like ordinary Strich wings, but they're actually Divine Strich Wings! And that changes everything.":
        "Bunlar sıradan Strich kanatlarına benzeyebilir ama aslında Divine Strich Wings! Bu da her şeyi değiştirir.",
    "This amulet may look like an Al Howin's Treat, but that's no reason to eat it.":
        "Bu tılsım Al Howin's Treat'e benzeyebilir ama bu, onu yemek için bir neden değildir.",
    "This bracelet washed up on Moon Island, along with some Possessed Epaulettes. It can now be worn on your finger.":
        "Bu bilezik bazı Possessed Epaulettes ile birlikte Moon Adası kıyısına vurdu. Artık parmağına takılabilir.",
    "This copy of a Stele of Murmurs engraving lets off a light rustle in the wind.":
        "Stele of Murmurs gravürünün bu kopyası rüzgârda hafifçe hışırdar.",
    "This hammer is a dark version of the Moon Hammer that you collected on Moon Island. It's incredibly sturdy, and according to the legends, allows solid volcanic rock to be easily broken.":
        "Bu çekiç, Moon Adası'nda topladığın Moon Hammer'ın karanlık bir sürümüdür. İnanılmaz derecede sağlamdır ve efsanelere göre sert volkanik kayaları kolayca kırar.",
    "This key can be used to unlock an Intervention Stele level in the Badgerox, Dor'Mor, Dreggon, and Ethernal dungeons.":
        "Bu anahtar Badgerox, Dor'Mor, Dreggon ve Ethernal zindanlarında bir Intervention Stele seviyesinin kilidini açar.",
    "This key can be used to unlock an Intervention Stele level in the Bubourg and Gerbean dungeons.":
        "Bu anahtar Bubourg ve Gerbean zindanlarında bir Intervention Stele seviyesinin kilidini açar.",
    "This key can be used to unlock an Intervention Stele level in the Octopus Crew, Deathburn, Bitter-Hammer, Abyssal Creeper, and Foggernaut dungeons.":
        "Bu anahtar Octopus Crew, Deathburn, Bitter-Hammer, Abyssal Creeper ve Foggernaut zindanlarında bir Intervention Stele seviyesinin kilidini açar.",
    "This key can be used to unlock an Intervention Stele level in the Octopus Crew, Deathburn, and Bitter-Hammer dungeons.":
        "Bu anahtar Octopus Crew, Deathburn ve Bitter-Hammer zindanlarında bir Intervention Stele seviyesinin kilidini açar.",
    "This key can be used to unlock an Intervention Stele level in the Phytomorph, Voidivion, Horridemon, Streye, and Destroyer dungeons.":
        "Bu anahtar Phytomorph, Voidivion, Horridemon, Streye ve Destroyer zindanlarında bir Intervention Stele seviyesinin kilidini açar.",
    "This little Golden Bow Wow is so cute.":
        "Bu küçük Golden Bow Wow çok tatlı.",
    "Want to break free from the mold? You need the Great Ice Cape.":
        "Kalıpları kırmak mı istiyorsun? Sana gereken şey Great Ice Cape.",
    "Wear your Lil Challenger Belt proudly!":
        "Lil Challenger Belt'i gururla tak!",
    "What could be sexier than a holey flour sack? Why, this Farmer Shirt, of course!":
        "Delik deşik bir un çuvalından daha çekici ne olabilir? Elbette Farmer Shirt!",
    "Who knows which figurine from the  Brotherhood of the Tofu you might find hiding in this incredible Trinket Box?":
        "Bu inanılmaz Trinket Box'ta Brotherhood of the Tofu üyelerinden hangisinin figürünü bulacağını kim bilebilir?",
    "You can recognize Royal Grawfish by their huge, razor-sharp pincers. It's not unusual for a fisherman to lose his fingers while trying to reel one in.":
        "Royal Grawfish'leri devasa, jilet keskinliğindeki kıskaçlarından tanıyabilirsin. Bir balıkçının onları çekerken parmaklarını kaybetmesi alışılmadık değildir.",
    "You can try as you might to stand head over shoulders above the others but at the end of the day these are Dirty Scoundrel Epaulettes.":
        "Başkalarından bir baş ve omuz yukarıda durmaya ne kadar çalışırsan çalış, günün sonunda bunlar Dirty Scoundrel Epaulettes.",
    "You just want to take these Blood-Stained Epaulettes off, now!":
        "Bu Blood-Stained Epaulettes'i hemen çıkarmak istiyorsun!",
    "You just want to take these they're Blood-Stained Epaulettes and you just want them off!":
        "Bunlar Blood-Stained Epaulettes; tek istediğin onları hemen çıkarmak!",
    "You made a good choice turning that Strich into epaulettes rather than nuggets. they're Viscous Epaulettes and now they won't come off!":
        "O Strich'i lokma yapmak yerine apolete dönüştürerek iyi bir seçim yaptın. Artık Viscous Epaulettes oldular ve bir daha çıkmayacaklar!",
    "You'll be enthusiastic about Nutellarva Skin.":
        "Nutellarva Skin seni heyecanlandıracak.",
    "Your Charming Bow Meow bows and meows most bewitchingly, making Bow Meowettes' hearts melt and lashes bat twitchingly.":
        "Charming Bow Meow'un büyüleyici biçimde eğilip miyavlaması Bow Meowette'lerin kalplerini eritip kirpiklerini titretiyor.",
}

SOURCE_EXACT.update(ITEM_DESCRIPTION_EXACT)

# Aynı İngilizce kaynağın farklı dosyalarda eski/bozuk makine çevirileriyle
# çoğaldığı doğrulanmış kopyalar. Kısa ve bağlama göre değişebilen Home/Area/
# Play gibi etiketler bilerek bu listede değildir.
CONSISTENCY_EXACT = {
    "Merriment": "Neşe",
    "Name": "Ad",
    "Achievement Monitoring": "Başarım Takibi",
    "1st Rank": "1. Sıra",
    "Waiting": "Bekleniyor",
    "Government": "Hükümet",
    "Skin": "Ten",
    "Battle": "Dövüş",
    "Politics": "Siyaset",
    "Trade": "Ticaret",
    "Vicinity": "Yakın Çevre",
    "Regenerates [#1] HP every 5 seconds out of combat":
        "Dövüş dışında her 5 saniyede [#1] Can Puanı yeniler",
    "is attracted by [#1] cell{[=1]?:s}":
        "[#1] {[=1]?hücre çekilir:hücre çekilir}",
    "% Heals performed": "% Yapılan İyileştirme",
    "Guild Standard Emote": "Guild Standard İfadesi",
    "Display Windows": "Vitrinleri Göster",
    "Crafting Machines": "Üretim Makineleri",
    "Is it lucky? Neigh, but it looks lovely!": "Şans getirir mi? İiih, ama çok güzel görünüyor!",
    "Cooool, man!": "Çooook havalı, dostum!",
    "Owning a Gigantegg in perfect condition is as rare as it is cumbersome. Don't be surprised if you feel little bird pecks coming from inside it. ": (
        "Mükemmel durumdaki bir Gigantegg'e sahip olmak, hantal olduğu kadar nadirdir. İçinden küçük kuş gagaları "
        "hissedersen şaşırma."
    ),
    "Aralia Spinosa's favorite jewel, this magnificent blue ring (which is a bit on the grotty side) will allow you to lead your enemies into the mud with ease.": (
        "Aralia Spinosa'nın en sevdiği mücevher olan bu muhteşem mavi yüzük (biraz çamurlu olsa da) düşmanlarını "
        "kolayca çamura sürüklemeni sağlayacak."
    ),
    "These little blades only slice up Boowolves when there is a full moon. The rest of the time they're completely and utterly useless.": (
        "Bu küçük bıçaklar Boowolf'ları yalnızca dolunayda keser. Diğer zamanlarda hiçbir işe yaramaz."
    ),
    "There must be at least fifty shades of blood on this cloak, from fruity Eniripsa blood to wood-scented Sadida blood, not forgetting a few healthy spatters of milky Pandawa blood.": (
        "Bu pelerinin üzerinde en az elli ton kan olmalı: meyvemsi Eniripsa kanından odun kokulu Sadida kanına, "
        "hatta birkaç sağlıklı sütümsü Pandawa kanı sıçramasına kadar."
    ),
    "This breastplate appears to have been cast in a single piece. It protects against the often violent discharges that arise from metalwork.": (
        "Bu göğüslük tek parça hâlinde dökülmüş gibi görünüyor. Metal işçiliği sırasında sıkça oluşan şiddetli "
        "boşalmalara karşı koruma sağlar."
    ),
    "This miniature releases little puffs of noxious gas to remind you of your adventures.":
        "Bu minyatür, maceralarını hatırlatmak için küçük zehirli gaz bulutları salar.",
    "An old Lenald needs to know when to cover his neck so he doesn't become sick as a dog.":
        "Yaşlı bir Lenald, fena hâlde hastalanmamak için boynunu ne zaman örtmesi gerektiğini bilmeli.",
    "An ideal accessory for the highly effective Condemner on the go.":
        "Hareket hâlindeki son derece etkili Condemner için ideal bir aksesuar.",
    "Adventures who wear this cloak descend slowly into madness until they give themselves over completely to Dementya. Equip with moderation.": (
        "Bu pelerini giyen maceracılar, kendilerini bütünüyle Dementya'ya teslim edene dek yavaş yavaş deliliğe "
        "sürüklenir. Ölçülü kullanın."
    ),
    "Competitive: Battle of the Flying Monsters": "Rekabet: Uçan Canavarların Savaşı",
    "Race: Battle of the Flying Monsters": "Yarış: Uçan Canavarların Savaşı",
    "Solo: Battle of the Flying Monsters": "Tekli: Uçan Canavarların Savaşı",
    "Competitive: I Saw Wild Tofus Passing By": "Rekabet: Yabani Tofu'ların Geçtiğini Gördüm",
    "Competitive: The Return of the Killer Schneks": "Rekabet: Katil Schnek'lerin Dönüşü",
    "Competitive: The Chant of the Bellaphones": "Rekabet: Bellaphone'ların Ezgisi",
    "Solo: Sacled Amalanth": "Tekli: Sacled Amalanth",
    "+1 AP saved": "+1 AP biriktirildi",
    "+2 AP saved": "+2 AP biriktirildi",
    "[li]\\nLength: ": "[li]\\nSüre: ",
    "[pl][#1]% health stolen": "[pl][#1]% Can çalar",
    "[$1ef]\\n\\n+1 level of [st7651] on the caster\\n\\nAt level 2 of [st7651]:\\n[pl]The caster regains 3 AP": (
        "[$1ef]\\n\\nKullanıcı 1 seviye [st7651] kazanır\\n\\n[st7651] 2. seviyedeyse:"
        "\\n[pl]Kullanıcı 3 AP geri kazanır"
    ),
    "Master of Luck": "Şans Ustası",
    "Emotional Incarnate": "Duygunun Vücut Bulmuş Hâli",
    "Venerable Spirit": "Saygıdeğer Ruh",
    "Wakfu Era Prophet": "Wakfu Çağı Kahini",
    "Nox's Supreme Setback": "Nox'un En Büyük Yenilgisi",
    "Temple of Scriptures": "Kutsal Yazılar Tapınağı",
    "Missy Amulet": "Missy Amulet",
    "Look closer": "Daha Yakından Bak",
    "Crate of Merchandise": "Ticari Mal Sandığı",
    "Crobak bait": "Crobak Yemi",
    "Grand Orrok's Warehouse": "Grand Orrok'un Deposu",
    "Trool Fair": "Trool Panayırı",
    "Bitter-Hammer Cavern": "Acı-Çekiç Mağarası",
    "The Black Crow's Lair": "Kara Karga'nın İni",
    "The Royal Pasturizer": "Kraliyet Pastörizatörü",
    "Ambassador's Wing": "Büyükelçinin Kanadı",
    "Kween's Gawden": "Kween'in Bahçesi",
    "Jelly Dungeon": "Jöle Zindanı",
    "Flaxhid's Sanctuary": "Flaxhid'in Sığınağı",
    "Xelorium - Present": "Xelorium - Günümüz",
    "Temple of the Grand Orrok": "Grand Orrok Tapınağı",
    "High Wind Plateau": "Yüksek Rüzgâr Platosu",
    "Ogrest's Cult's Blast Hole": "Ogrest Tarikatı'nın Patlama Çukuru",
    "Kanniball Dungeon": "Kanniball Zindanı",
    "Badgeroxes' Lair": "Badgerox'ların İni",
    "Iced-Over Crest": "Donmuş Sırt",
    "Dreggons' Sanctuary": "Dreggonların Sığınağı",
    "Wellspring of Evil": "Kötülüğün Kaynağı",
    "Charred Forest": "Yanık Orman",
    "Vandalophrenic Dungeon": "Vandalofren Zindanı",
    "Octopus Crew Dungeon": "Ahtapot Mürettebatı Zindanı",
    "Abyssal Creeper Dungeon": "Uçurum Sarmaşığı Zindanı",
    "Bitter-Hammer Dungeon": "Acı-Çekiç Zindanı",
    "Cosmo Canyon": "Kozmo Kanyonu",
    "Grambos' Desolation": "Gramboların Issızlığı",
    "Dirty Trouffe Estate": "Kirli Trouffe Malikânesi",
    "Boarthroom Estate": "Boarthroom Malikânesi",
    "Abandoned Scarapit": "Terk Edilmiş Scarapit",
    "Elite Riktus Dungeon": "Seçkin Riktus Zindanı",
    "The Tofuhouse": "Tofu Evi",
    "Royal Pasturizer": "Kraliyet Pastörizatörü",
    "Pack Leader": "Sürü Lideri",
    "Puddle": "Su Birikintisi",
    "Down and Out": "Nakavt",
    "Pastryfaction Aura": "Pastacılık Aurası",
    "Upwoaw at the Wa's Castle": "Wa'nın Kalesinde Kargaşa",
    "Nations - Chapter 1": "Uluslar - Bölüm 1",
    "Nations - Chapter 2": "Uluslar - Bölüm 2",
    "Nations - Chapter 3": "Uluslar - Bölüm 3",
    "Nations - Chapter 4": "Uluslar - Bölüm 4",
    "Nations - Chapter 5": "Uluslar - Bölüm 5",
    "Mount Zinit - Chapter 2": "Zinit Dağı - Bölüm 2",
    "Mount Zinit - Chapter 3": "Zinit Dağı - Bölüm 3",
    "Adjustable Level": "Ayarlanabilir Seviye",
    "Mount Zinit - Wild Beach": "Zinit Dağı - Vahşi Sahil",
    "Mount Zinit - Schnek Cave": "Zinit Dağı - Schnek Mağarası",
    "Mount Zinit - Chapter 4": "Zinit Dağı - Bölüm 4",
    "Mineral Tower": "Maden Kulesi",
    "Eternal Mineral Tower": "Ebedî Maden Kulesi",
    "Imperfect Mineral Tower": "Kusurlu Maden Kulesi",
    "Divine Mineral Tower": "İlahi Maden Kulesi",
    "Ebony Dofus": "Ebony Dofus",
    "The Bestial Pact": "Canavarca Anlaşma",
    "Crimson Season": "Kızıl Mevsim",
    "Snowbound Treasure": "Karla Kaplı Hazine",
    "Spring Treasure": "Bahar Hazinesi",
    "Treasure on Stilts": "Kazıklar Üstündeki Hazine",
    "Dunic Treasure": "Kumul Hazinesi",
    "Defeat Gengas Kin": "Gengas Kin'i yen",
    "Defeat Koko Rico": "Koko Rico'yu yen",
    "Eat all the Orbs without killing any Jellies": "Hiç Jelly öldürmeden bütün Orb'ları ye",
    "Summon 15 Peashooters": "15 Peashooter çağır",
    "Amakna - Amakna Village": "Amakna - Amakna Köyü",
    "Bonta Ruins - Bonta": "Bonta Harabeleri - Bonta",
    "Brakmar Village - Brakmar": "Brakmar Köyü - Brakmar",
    "Sufokia Village - Sufokia": "Sufokia Köyü - Sufokia",
    "Seaside - East": "Deniz Kenarı - Doğu",
    "Bwork Village": "Bwork Köyü",
    "Mountain": "Dağ",
    "Kelba Zaap": "Kelba Zaapı",
    "Infiltwation": "Sızma",
    "Invulnerable": "Yaralanmaz",
    "Survival": "Hayatta Kalma",
    "Dorsum": "Sırt",
    "Bwork Madness": "Bwork Çılgınlığı",
    "Bwork Exhilaration": "Bwork Coşkusu",
    "Excarnal Possession": "Bedensiz Ele Geçirme",
    "Sedentary": "Hareketsiz",
    "Tremblor": "Sarsıntı",
    "Demon Hunter": "İblis Avcısı",
    "Tripled": "Üçe Katlandı",
    "Doubled": "İkiye Katlandı",
    "Unlockable": "Kilidi Açılabilir",
    "Tenderised": "Yumuşatılmış",
    "Treasure Hunter": "Hazine Avcısı",
    "Liberator": "Kurtarıcı",
    "Mimic": "Taklitçi",
    "Symbiote": "Simbiyot",
    "Reincarnation": "Yeniden Doğuş",
    "Featherweight": "Tüy Sıklet",
    "Waning": "Küçülme",
    "Shrill Airwhisp": "Tiz Hava Fısıltısı",
    "Shrill Waterwhisp": "Tiz Su Fısıltısı",
    "Shrill Firewhisp": "Tiz Ateş Fısıltısı",
    "Shrill Earthwhisp": "Tiz Toprak Fısıltısı",
    "Generator": "Jeneratör",
    "Anti-Abuse": "Kötüye Kullanımı Önleme",
    "Lock Gain": "Kilitleme Kazancı",
    "Clockmakers": "Saat Ustaları",
    "The target has been motivated by the Standard-Bearing Whisperer.":
        "Hedef, Standard-Bearing Whisperer tarafından motive edilir.",
    "Do not inflict Earth damage on enemies": "Düşmanlara Toprak hasarı verme",
    "Plump": "Tombul",
    "Colossal": "Devasa",
    "Sensual": "Cazibeli",
    "Disciple": "Mürit",
    "Lock": "Kilitleme",
    "Force of Will": "İrade",
    "Call for help": "Yardım İste",
    "Poison": "Zehirle",
    "Encourage": "Cesaretlendir",
    "Heal": "İyileştir",
    "Scissors": "Makas",
    "Ultimate Boss": "Nihai Baş Canavar",
    "Relic": "Yadigâr",
    "Recycling": "Geri Dönüşüm",
    "Runes": "Rünler",
    "Sit": "Otur",
    "Common": "Sıradan",
    "Mythical": "Mitik",
    "Deactivated": "Devre Dışı",
    "Nation Bonus": "Ulus Bonusu",
    "Tokens": "Jetonlar",
    "Team search": "Takım Arama",
    "Let's see...": "Bakalım...",
    "How turnip a seed": "Bir Tohum Nasıl Şalgama Dönüşür?",
    "Spell Book": "Büyü Kitabı",
    "Famished Mimic": "Aç Mimic",
}

SOURCE_EXACT.update(CONSISTENCY_EXACT)

# Aynı anahtarın JAR içinde eski ve yeni dünya haritası metinleriyle tekrar
# kullanıldığı yerlerde anahtar bazlı JSON tek başına yeterli değildir. Bu
# kaynak-değer sözlüğü her kopyayı kendi görünen metnine göre çevirir; yalnız
# güvenle ayrılabilen coğrafi/yönsel ifadeleri kapsar, özel adları korur.
WORLD_VALUE_EXACT = {
    "Amakna - Amakna Village": "Amakna - Amakna Köyü",
    "Bonta Ruins - Bonta": "Bonta Harabeleri - Bonta",
    "Brakmar Village - Brakmar": "Brakmar Köyü - Brakmar",
    "Sufokia Village - Sufokia": "Sufokia Köyü - Sufokia",
    "Heraldtopia - Devs' Haven World": "Heraldtopia - Geliştiricilerin Haven World'ü",
    "Dev-Land": "Geliştirici Diyarı",
    "Jumpin' Jungle, Kokokobana - Sufokia": "Zıplayan Orman - Kokokobana - Sufokia",
    "Jumpin' Jungle - Kokokobana": "Zıplayan Orman - Kokokobana",
    "Unknown Island, Center": "Bilinmeyen Ada - Merkez",
    "Unknown Island, East": "Bilinmeyen Ada - Doğu",
    "Unknown Island, West": "Bilinmeyen Ada - Batı",
    "Wild Estate East": "Vahşi Malikâne - Doğu",
    "Wild Estate West": "Vahşi Malikâne - Batı",
    "Bay - Center": "Körfez - Merkez",
    "Bay - East": "Körfez - Doğu",
    "Bay - Southeast": "Körfez - Güneydoğu",
    "Seaside - East": "Deniz Kenarı - Doğu",
    "Seaside - South": "Deniz Kenarı - Güney",
    "Shhhudoku Kingdom Center": "Shhhudoku Krallığı - Merkez",
    "Shhhudoku Kingdom, Center-West": "Shhhudoku Krallığı - Orta Batı",
    "Shhhudoku Kingdom North": "Shhhudoku Krallığı - Kuzey",
    "Shhhudoku Kingdom South": "Shhhudoku Krallığı - Güney",
    "Monk Island South": "Keşiş Adası - Güney",
    "Monk Island, East Central": "Keşiş Adası - Orta Doğu",
    "Monk Island, West Central": "Keşiş Adası - Orta Batı",
    "Monk Island, Southern Path": "Keşiş Adası - Güney Yolu",
    "Bilbiza Center": "Bilbiza - Merkez",
    "Bilbiza South": "Bilbiza - Güney",
    "Bilbiza, Northeast": "Bilbiza - Kuzeydoğu",
    "Bilbiza, Northwest": "Bilbiza - Kuzeybatı",
    "Forfut Center": "Forfut - Merkez",
    "Forfut Jetty": "Forfut İskelesi",
    "Forfut North": "Forfut - Kuzey",
    "Forfut South": "Forfut - Güney",
    "Kelba Jetty": "Kelba İskelesi",
    "Kelba North": "Kelba - Kuzey",
    "Kelba South": "Kelba - Güney",
    "Kelba Zaap": "Kelba Zaapı",
    "Wabbit Island Center": "Wabbit Adası - Merkez",
    "Wabbit Island South": "Wabbit Adası - Güney",
    "Sadida Kingdom Jetty": "Sadida Krallığı İskelesi",
    "Sadida Kingdom South": "Sadida Krallığı - Güney",
    "Gobballfield - Amakna": "Gobball Tarlası - Amakna",
    "Gobballfield": "Gobball Tarlası",
    "Amaknian Fire of Love": "Amakna Aşk Ateşi",
    "Bontarian Fire of Love": "Bonta Aşk Ateşi",
    "Brakmarian Fire of Love": "Brakmar Aşk Ateşi",
    "Sufokian Fire of Love": "Sufokia Aşk Ateşi",
    "Wabbit Islands": "Wabbit Adaları",
    "Owl Council": "Baykuş Konseyi",
    "Mount Zinit": "Zinit Dağı",
    "Trool Fair - Rock-Paper-Scissors Contest": "Trool Panayırı - Taş-Kâğıt-Makas Yarışması",
    "Trool Fair - Dark Vlad's Maze": "Trool Panayırı - Dark Vlad'ın Labirenti",
    "Trool Fair - Gold Rush": "Trool Panayırı - Altına Hücum",
    "Trool Fair - Gladiatrool": "Trool Panayırı - Gladiatrool",
    "Trool Fair - Ghostof Mansion": "Trool Panayırı - Ghostof Malikânesi",
    "Trool Fair - Enutrof Game": "Trool Panayırı - Enutrof Oyunu",
    "Trool Fair - Mystic Moe's": "Trool Panayırı - Mystic Moe",
    "Trool Fair - Dopple Manor": "Trool Panayırı - Dopple Malikânesi",
    "Trool Fair - Cupe 'Em Up": "Trool Panayırı - Küpleri Parçala",
    "Lemon Dimension": "Limon Boyutu",
    "Blue Raspberry Dimension": "Mavi Ahududu Boyutu",
    "Sea of Clouds": "Bulutlar Denizi",
    "Last Chance Saloon": "Son Şans Meyhanesi",
    "The Wabbit Hutch": "Wabbit Kulübesi",
    "Old Gallewy": "Eski Galeri",
    "Harebourg's Site": "Harebourg'un Sahası",
    "Brakmarian Excavation Site": "Brakmar Kazı Alanı",
    "Northwest": "Kuzeybatı",
    "Northeast": "Kuzeydoğu",
    "Southeast": "Güneydoğu",
    "Downtown": "Şehir Merkezi",
    "Dig site": "Kazı Alanı",
    "Cawwot - Northwest": "Cawwot - Kuzeybatı",
    "Forfut - Secrets": "Forfut - Sırlar",
    "Frigost - Secrets": "Frigost - Sırlar",
    "Astrub - Secrets": "Astrub - Sırlar",
    "Somewhere in Srambad...": "Srambad'da Bir Yer...",
    "Enurado Front Desk": "Enurado Danışma Masası",
    "Cap'n Atcha's Haven": "Cap'n Atcha'nın Sığınağı",
    "Sadida Dimension": "Sadida Boyutu",
    "Unknown area": "Bilinmeyen Bölge",
    "Vaporous Cloud": "Buharlı Bulut",
    "Somewhere...": "Bir Yerlerde...",
    "Ush's Hiding Place": "Ush'un Saklanma Yeri",
    "The Black Crow's Locker": "Kara Karga'nın Dolabı",
    "Archaosological Excavation Site": "Arkaosolojik Kazı Alanı",
    "The Ogre's Salines - Night": "Ogr'un Tuzlaları - Gece",
    "Immaterial University of Bonta": "Bonta Maddesiz Üniversitesi",
    "Moon - Dofus Era": "Moon - Dofus Çağı",
    "Xelorium - Dofus Era": "Xelorium - Dofus Çağı",
    "Amakna - Dofus Era": "Amakna - Dofus Çağı",
    "Astrub - Dofus Era": "Astrub - Dofus Çağı",
    "Bonta - Dofus Era": "Bonta - Dofus Çağı",
    "Brakmar - Dofus Era": "Brakmar - Dofus Çağı",
    "Sufokia - Dofus Era": "Sufokia - Dofus Çağı",
    "Enurado - Dofus Era": "Enurado - Dofus Çağı",
    "Srambad - Dofus Era": "Srambad - Dofus Çağı",
    "Event Area": "Etkinlik Alanı",
    "Mount Zinit Summit": "Zinit Dağı Zirvesi",
    "Sufokia - Interiors": "Sufokia - İç Mekânlar",
    "Amakna - Interiors": "Amakna - İç Mekânlar",
    "Bonta - Interiors": "Bonta - İç Mekânlar",
    "Brakmar - Interiors": "Brakmar - İç Mekânlar",
    "The Great Escort": "Büyük Eskort",
    "The Heroic Great Escort": "Kahramanca Büyük Eskort",
    "Capture the Flowers": "Çiçekleri Ele Geçir",
    "Heroic Capture the Flowers": "Kahramanca Çiçekleri Ele Geçir",
    "Free-for-Alls": "Herkes Tek",
    "Osamodas's Throne": "Osamodas'ın Tahtı",
    "Osamosa Antechamber": "Osamosa Antresi",
    "Osamosa - Interiors": "Osamosa - İç Mekânlar",
    "Strange Place": "Tuhaf Yer",
    "Weird Place": "Garip Yer",
    "Inside": "İçerisi",
    "Memory of Another World": "Başka Bir Dünyanın Hatırası",
    "Final Moment of the Dream": "Rüyanın Son Anı",
    "Proving Ground": "Talim Sahası",
    "Mysterious Pyramid": "Gizemli Piramit",
    "Zurikat Hut": "Zurikat Kulübesi",
    "Bwork Herd": "Bwork Sürüsü",
    "Nox's Clock": "Nox'un Saati",
    "Neo Vessel": "Neo Gemi",
}


ENV_TITLE_TRANSLATIONS = {
    "Bombs Go Boom": "Bombalar Patlıyor",
    "I Saw Wild Tofus Passing By": "Yabani Tofu'ların Geçtiğini Gördüm",
    "Dark Hero of Death": "Ölümün Karanlık Kahramanı",
    "Vestiges of the Old Days": "Eski Günlerin Kalıntıları",
    "Claws of the Canyon": "Kanyonun Pençeleri",
    "Mascot of a Faraway Crew": "Uzak Bir Mürettebatın Maskotu",
    "The Shushus of Sthulhu": "Sthulhu'nun Shushu'ları",
    "The Flowers of Evil": "Kötülük Çiçekleri",
    "Return of the Whirly Knurly": "Whirly Knurly'nin Dönüşü",
    "The Zeros of the Past": "Geçmişin Sıfırları",
    "The Chant of the Bellaphones": "Bellaphone'ların Ezgisi",
    "The Return of the Killer Schneks": "Katil Schnek'lerin Dönüşü",
    "The Call of Koutoulou": "Koutoulou'nun Çağrısı",
    "An Egg Worthy of the Greatest": "En Büyüklere Layık Bir Yumurta",
    "The Pot of Discord": "Anlaşmazlık Kazanı",
    "Like a Flock of Crobaks": "Bir Crobak Sürüsü Gibi",
    "The Army of the Less than Living": "Yaşayanlardan Sayılmayanların Ordusu",
    "Like Dreadful Gluttons of the Sea": "Denizin Korkunç Oburları Gibi",
    "In Search of Lost Bworker": "Kayıp Bworker'ın Peşinde",
    "Return of the Polters": "Polterlerin Dönüşü",
    "The Desolation of Smaud": "Smaud'un Çoraklığı",
    "Battle of the Flying Monsters": "Uçan Canavarların Savaşı",
    "Top of the Lollipops": "Lolipopların Zirvesi",
    "Night of the Boowolves": "Boowolf'ların Gecesi",
    "Seed of Chunky": "Chunky'nin Tohumu",
    "The Leaves of Others": "Başkalarının Yaprakları",
    "Out of Time": "Zaman Tükendi",
    "Pile of Ashes": "Kül Yığını",
    "Army of Knights": "Şövalyeler Ordusu",
    "Plenty of Opportunites, They Said": "\"Fırsat Çok,\" Dediler",
    "Return of the Larvae": "Larvaların Dönüşü",
    "The School of Champions": "Şampiyonlar Okulu",
    "The Flower of Good": "İyilik Çiçeği",
}

MODE_LABELS = {
    "Collaborative": "İş Birliği",
    "Competitive": "Rekabet",
    "Race": "Yarış",
    "Solo": "Tekli",
}

ACHIEVEMENT_TITLES = {
    "Feathers of Gold": "Altın Tüyler",
    "War of Whirlcraft": "Whirlcraft Savaşı",
    "Sanctuary of Oktapodas": "Oktapodas Sığınağı",
}

PROFESSIONS = {
    "Armorer": "Zırh Ustası",
    "Chef": "Aşçı",
    "Handyman": "Tamirci",
    "Jeweler": "Kuyumcu",
    "Leather Dealer": "Derici",
    "Tailor": "Terzi",
    "Weapons Master": "Silah Ustası",
}


def source_values() -> dict[str, str]:
    with zipfile.ZipFile(SOURCE_JAR) as archive:
        name = "texts_en.properties"
        if name not in archive.namelist():
            name = "texts_en_cleaned.properties"
        text = archive.read(name).decode("utf-8-sig")
    return {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in text.splitlines()
        if "=" in line and not line.startswith(("#", "!"))
    }


def load(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def save(path: Path, values: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(values, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def environment_title(source: str) -> str | None:
    mode = None
    base = source.strip()
    mode_match = re.match(r"^(Collaborative|Competitive|Race|Solo)\s*:\s*(.+)$", base)
    if mode_match:
        mode, base = mode_match.groups()
    horde_match = re.match(r"^(?:Hordes|Holdes|Packs) of (.+)$", base)
    if horde_match:
        translated = f"{horde_match.group(1)} Sürüleri"
    else:
        translated = ENV_TITLE_TRANSLATIONS.get(base)
    if translated is None:
        return None
    return f"{MODE_LABELS[mode]}: {translated}" if mode else translated


def pattern_translation(key: str, source: str) -> str | None:
    if key.startswith("content.16."):
        match = re.match(
            r"^Collect 100 of these fragments to create "
            r"(?:a pair of |an? )?([^.]+?)"
            r"( \(linked to the account\))?[.]{1,2}$",
            source,
        )
        if match:
            item_name, linked = match.groups()
            suffix = " (hesaba bağlı)." if linked else "."
            return f"Bu parçalardan 100 tane topla ve {item_name} oluştur{suffix}"

        match = re.match(r"^This scroll will teach you the recipe for (.+)$", source)
        if match:
            return f'Bu parşömen sana "{match.group(1)}" tarifini öğretir.'

        match = re.match(
            r"^When used alongside other items, (?:these |this |the )?(.+?) "
            r"will make you into an 'honest' citizen of the Nation of (.+)[.]$",
            source,
        )
        if match:
            item_name, nation = match.groups()
            return (
                f"Diğer eşyalarla birlikte kullanıldığında {item_name}, "
                f"{nation} Ulusu'nun 'dürüst' bir vatandaşı olmanı sağlar."
            )

    blueprint_patterns = (
        (r'^This blueprint will teach you the recipe for the item \"(.+)\" for the (.+) profession[.]$', "eşya"),
        (r'^This blueprint will teach you the recipe for the \"(.+)\" item for the (.+) profession[.]$', "eşya"),
        (r'^This blueprint will teach you the recipe for the relic \"(.+)\" for the (.+) profession[.]$', "yadigâr"),
    )
    for pattern, item_type in blueprint_patterns:
        match = re.match(pattern, source)
        if match:
            item_name, profession = match.groups()
            profession_tr = PROFESSIONS.get(profession, profession)
            return f'Bu taslak, {profession_tr} mesleğinde \"{item_name}\" {item_type} tarifini öğretir.'

    match = re.match(r'^This scroll will teach you the \"(.+)\" emote[.]$', source)
    if match:
        return f'Bu tomar \"{match.group(1)}\" ifadesini öğretir.'

    match = re.match(r'^Read(?: the)? \"(.+)\"$', source)
    if match:
        return f'\"{match.group(1)}\" eşyasını oku'

    match = re.match(r'^I\'d like to recover the item \"(.+)\"[.]$', source)
    if match:
        return f'\"{match.group(1)}\" eşyasını geri almak istiyorum.'

    match = re.match(r'^Craft a \"(.+)\" during Spring Has Sprung$', source)
    if match:
        return f'Spring Has Sprung sırasında \"{match.group(1)}\" üret'

    environmental = environment_title(source)
    if environmental is not None and (key.startswith("content.26.") or source.startswith("Collaborative")):
        return environmental

    match = re.match(r'^Complete the environmental quest(?:\s*:\s*|\s+)[\"“]?(.+?)[\"”]?[.]?$', source)
    if match:
        title = environment_title(match.group(1))
        if title:
            return f'\"{title}\" çevre görevini tamamla'

    match = re.match(r"^Complete the achievement: (Feathers of Gold|War of Whirlcraft|Sanctuary of Oktapodas) ([IVX]+)$", source)
    if match:
        return f'\"{ACHIEVEMENT_TITLES[match.group(1)]} {match.group(2)}\" başarımını tamamla'

    if source == "Complete the Sanctuary of Oktapodas Dungeon":
        return "Oktapodas Sığınağı Zindanı'nı tamamla"

    match = re.match(r"^Take (\d+) (Essences? of .+) to the Guild of Hunters[.]?$", source)
    if match:
        return f"{match.group(1)} {match.group(2)} eşyasını Avcılar Loncası'na götür"

    match = re.match(r"^Obtain (\d+) (Flasks? of Rum) from the (.+)$", source)
    if match:
        return f"{match.group(3)} adlı yaratıklardan {match.group(1)} {match.group(2)} elde et"

    if source == "Go back to see the Frightened Bwork to create the Essence of Bwork":
        return "Essence of Bwork üretmek için Frightened Bwork'ü yeniden ziyaret et"
    if source == "Destroy the contents of the case of Seeds of Chaos":
        return "Seeds of Chaos kutusunun içindekileri yok et"
    if source == "I'll go and get you some Essence of Northern Chafer.":
        return "Gidip sana biraz Essence of Northern Chafer getireceğim."
    return None


def validate_source_map(sources: dict[str, str]) -> None:
    values = set(sources.values())
    missing_sources = sorted(source for source in SOURCE_EXACT if source not in values)
    missing_keys = sorted(key for key in KEY_EXACT if key not in sources)
    if missing_sources or missing_keys:
        raise RuntimeError(
            f"Düzeltme güncel kaynakla eşleşmiyor; kaynak={len(missing_sources)}, anahtar={len(missing_keys)}"
        )


def normalize_target_typography(value: str, source: str = "") -> str:
    """Apply Turkish-safe spacing fixes without touching WAKFU tokens."""
    value = re.sub(r"(?<![,.;!?])[ \t]+([,.;!])", r"\1", value)
    # Some gender conditionals in Ankama's source deliberately contain a
    # space between the closing bracket and question mark: ``{[1*] ?e:}``.
    # Preserve that byte-for-byte while still fixing ordinary prose such as
    # ``Neden ?``.
    value = re.sub(r"(?<!\])[ \t]+\?", "?", value)
    value = re.sub(r"%[ \t]+(?=\d)", "%", value)
    value = re.sub(r"(?<=[^\W\d_])%(?=\d)", " %", value)
    source_bang_runs = [len(run) for run in re.findall(r"!{2,}", source)]
    if source_bang_runs:
        maximum = max(source_bang_runs)
        value = re.sub(rf"!{{{maximum + 1},}}", "!" * maximum, value)
    source_question_runs = [len(run) for run in re.findall(r"\?{2,}", source)]
    if source_question_runs:
        maximum = max(source_question_runs)
        value = re.sub(rf"\?{{{maximum + 1},}}", "?" * maximum, value)
    return value


def main() -> int:
    sources = source_values()
    validate_source_map(sources)
    project = load(PROJECT)
    manual = load(MANUAL)
    terminology = load(TERMINOLOGY)
    changes = 0
    terminology_changes = 0
    changed_keys: list[str] = []
    removed_protected_names = 0

    term_values = terminology.setdefault("values", {})
    if not isinstance(term_values, dict):
        raise RuntimeError("Terim sözlüğündeki values bölümü nesne olmalıdır")
    for source, target in WORLD_VALUE_EXACT.items():
        if term_values.get(source) != target:
            term_values[source] = target
            changes += 1
            terminology_changes += 1

    for key, source in sources.items():
        # Protected title/state rows are always read directly from the English JAR.
        # Do not insert and then remove them during the same repair pass.
        if (
            key.startswith("content.3.")
            or (
                key.startswith("content.15.")
                and key not in TRANSLATABLE_INVENTORY_UI_KEYS
            )
            or (
                key.startswith("content.8.")
                and key not in TRANSLATABLE_COMBAT_STATE_KEYS
            )
            or key in EXTRA_PROTECTED_COMBAT_NAME_KEYS
        ):
            continue
        target = KEY_EXACT.get(key)
        if target is None:
            target = SOURCE_EXACT.get(source)
        if target is None:
            target = pattern_translation(key, source)
        if target is None and key in NORMALIZE_ONE_LEADING_SPACE_KEYS:
            current = project.get(key)
            if isinstance(current, str) and current.startswith("  \\n"):
                target = current[1:]
        candidate = target if target is not None else project.get(key)
        if isinstance(candidate, str):
            normalized = candidate
            for protected_name, replacements in REFERENCE_VARIANT_REPLACEMENTS.items():
                if protected_name not in source:
                    continue
                for old, new in replacements:
                    normalized = normalized.replace(old, new)
            for old, new in TARGET_VARIANT_REPLACEMENTS_BY_KEY.get(key, ()):
                normalized = normalized.replace(old, new)
            if key == "content.67.833":
                # Kaynaktaki -5990 yılı daha önce kaybolmuştu. Düz ``replace``
                # her çalıştırmada yeni bir eksi eklediğinden tüm eksi dizisini
                # tek ve kararlı bir işarete indir.
                normalized = re.sub(r"-*5990 yılında", "-5990 yılında", normalized)
            if normalized != candidate:
                target = normalized
        if target is None:
            continue
        for values in (project, manual):
            if values.get(key) != target:
                values[key] = target
                changes += 1
        changed_keys.append(key)

    # Noktalama ve yüzde işaretlerinin çevresindeki güvenli tipografi
    # kusurlarını bütün çevrilmiş metinlerde aynı biçimde düzelt.
    for values in (project, manual):
        for key, candidate in list(values.items()):
            normalized = normalize_target_typography(candidate, sources.get(key, ""))
            if normalized != candidate:
                values[key] = normalized
                changes += 1
                changed_keys.append(key)

    # Yetenek, savaş içi durum ve eşya başlıkları kullanıcının kuralı gereği her
    # zaman kaynak İngilizce metinden alınır. Eski çeviri belleğinde kalan
    # karşılıkları temizleyerek bütün katmanların aynı gerçeği görmesini sağla.
    for values in (project, manual):
        for key in list(values):
            if (
                key.startswith("content.3.")
                or (
                    key.startswith("content.15.")
                    and key not in TRANSLATABLE_INVENTORY_UI_KEYS
                )
                or (
                    key.startswith("content.8.")
                    and key not in TRANSLATABLE_COMBAT_STATE_KEYS
                )
                or key in EXTRA_PROTECTED_COMBAT_NAME_KEYS
            ):
                del values[key]
                changes += 1
                removed_protected_names += 1

    term_keys = terminology.setdefault("keys", {})
    if not isinstance(term_keys, dict):
        raise RuntimeError("Terim sözlüğündeki keys bölümü nesne olmalıdır")
    for key in list(term_keys):
        if (
            key.startswith("content.3.")
            or (
                key.startswith("content.15.")
                and key not in TRANSLATABLE_INVENTORY_UI_KEYS
            )
            or (
                key.startswith("content.8.")
                and key not in TRANSLATABLE_COMBAT_STATE_KEYS
            )
            or key in EXTRA_PROTECTED_COMBAT_NAME_KEYS
        ):
            del term_keys[key]
            changes += 1
            terminology_changes += 1

    save(PROJECT, project)
    save(MANUAL, manual)
    if terminology_changes:
        save(TERMINOLOGY, terminology)
    print(json.dumps({
        "changed_writes": changes,
        "terminology_writes": terminology_changes,
        "reviewed_keys": len(set(changed_keys)),
        "removed_protected_names": removed_protected_names,
        "project_keys": len(project),
        "manual_keys": len(manual),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
