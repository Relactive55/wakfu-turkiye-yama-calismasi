import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"
MANUAL = ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"
SOURCE_JAR = ROOT / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar"


FIXES = {
    # Ekran görüntülerinde görülen ek yetenek açıklamaları ve etkileri.
    "content.4.5049": "Sacrier kendisine her Flame Return uyguladığında Kilitleme ve Kaçınma değerlerini artırır. Ancak Flame Return etkileri daha güçlü olur.",
    "content.4.5193": "Sacrier doğal WP yenilenmesini kaybeder. Bunun yerine kendisine Flame Return uygulayarak WP kazanır.",
    "content.4.5194": "Sacrier, hareket büyülerinin WP bedelini AP bedeliyle değiştirir. Bir düşmanı büyüyle hareket ettirirse düşman doğrudan hasar alır. Sacrier kendisini hareket ettirirse Flame Return hasarı alır.",
    "content.4.5195": "Bu pasif, Sacrier'in Canını daha iyi yönetmesini sağlar. Sacrier bir hedefe hasar verdiğinde hedefin Can yüzdesi kendisininkinden yüksekse verdiği hasarın bir bölümüyle Can çalar. Sacrier'in Can yüzdesi hedefinkinden yüksekse kendisine Flame Return uygular.",
    "content.4.5249": "Ecaflip turunu bir düşmanın bitişiğinde tamamlarsa sonraki turda ücretsiz bir Feline Leap kazanır. Ancak Feline Leap tur başına üç yerine en fazla iki kez kullanılabilir.",
    "content.4.4682": "Calm/Exalted, Eliotrope'un iki temel mekaniğinden biridir. Bu büyü Calm ve Exalted modları arasında geçiş yapmasını sağlar. Eliotrope büyülerinin çoğu, etkin moda göre farklı etkiler uygular.",
    "content.4.4693": "Calm modunda Eliotrope hedefiyle yer değiştirir. Exalted modunda hedefin karşı tarafındaki simetrik hücreye ışınlanır. Büyü bir Portal üzerinden kullanılırsa yalnızca hasar veya iyileştirme uygulanır.",
    "content.4.4694": "Calm modunda Eliotrope savaş alanına bir Cataclysm alanı yerleştirir. Exaltation bir sonraki kez kullanıldığında bu alana ışınlanır ve çevresine yüksek hasar verir. Exalted modunda hedefe yüksek hasar verir.",
    "content.4.4790": "Iop hedefi hareketsiz bırakır; hedefin Direncini, aldığı iyileştirmeyi ve aldığı Zırhı 1 tur boyunca azaltır.",
    "content.4.4791": "Iop kendini ve çevresindeki müttefikleri iyileştirir. Aynı iyileştirme Iop'un Standard'ının çevresinde de uygulanır.",
    "content.4.4795": "Iop daha fazla Cana sahip olur; ancak Jump artık görüş hattı olmadan, engellerin arkasından kullanılamaz.",
    "content.4.4796": "Iop her turun başında 1 seviye Wrath kazanır, turun sonunda ise tüm Wrath seviyelerini kaybeder.",
    "content.4.4805": "Hedeflenen hücre Cra'nın Beacon'larından birine bitişikse kullanıcı o hücreye ışınlanır.",
    "content.4.6485": "Rogue'un Runaway modundaki element büyülerinin Menzili sabittir, ancak Rusty Blades üretir. Rusty Blades, Sneaky modunda hedefe birikebilen bir zehir uygulamak için tüketilir.",
    "content.4.6486": "Rogue, Sneaky modunda Zırh kazanmak için Powder tüketir.",
    "content.4.6492": "Rogue, Runaway modunda pençesiyle bir savaşçıya yaklaşır. Sneaky modunda hedefi kendine çeker, ardından hedefin arkasına geçer.",
    "content.4.6908": "Foggernaut hedeflenen hücreye sıçrar ve üzerinden geçtiği düşmanlara Su hasarı verir. Foggernaut'ta 2 seviye High Pressure varsa daha uzağa sıçrayabilir.",
    "content.4.7217": "Sacrier her WP kullandığında Can kazanır, ancak Flame Return hasarı alır.",
    "content.4.7959": "Bu pasif Feline Leap'i değiştirir. Büyü artık görüş hattı gerektirmeden ve daha uzun Menzilden kullanılabilir, ancak bedeli artar.",
    "content.33.197715": "Turun başında Sacrier <b>en az bir düşmandan</b> hasar aldıysa:\n[pl]<b>2 WP</b> yeniler\n\nBu etki, Sacrier hasar aldıktan sonra Canının %20'sini kaybettiğinde de uygulanır (Flame Return veya müttefiklerin verdiği hasar).",
    "content.33.197815": "10. seviyeden itibaren bir Punishment etkinken Sacrier Flame Return etkilerini tüketir:\n[pl][st4798]: Seviye başına %4 Verilen Hasar (1 tur)\n[pl][st4799]: İyileştirme: Seviye başına eksik Canın %4'ü",
    "content.33.317352": "Dövüş başında Ecaflip şu <b>büyülerin</b> kilidini açar:\n[pl][sp7953]\n[pl][sp7227]\n\n100'ün üzerindeki Kritik Vuruş değeri, Verilen Hasarı artırır ([st7999])\n\nTur sonunda Ecaflip 1 WP ve 20 [st3683] geri kazanır.",
    "content.33.353202": "4. Flame Return gerçekleştiğinde:\n[pl]2 WP",
    "content.33.353203": "Her 4 Flame Return etkisinde:\n[pl]2 WP\n\nDoğal WP yenilenmesi devre dışı bırakılır",
    "content.33.353367": "<b>Flame Return</b> etkileri Zırha dönüşür",
    "content.33.353416": "Sacrier kendisine [st4840] uyguladığında:\n[pl]Seviyesinin %100'ü kadar Kilitleme (1 tur, birikir)\n[pl]Seviyesinin %100'ü kadar Kaçınma (1 tur, birikir)\n\nFlame Return etkileri %20 artar",
    "content.33.357911": "Bir müttefik üzerinde kullanılırsa:\n[pl]Bitişik hedefleri 3 hücre iter\n[pl]2 MP (2 tur)\n[pl]%20 Kritik Vuruş (2 tur)\n\nBir düşman üzerinde kullanılırsa:\n[pl][st3683] tüketir\n[pl]Her Lucky Day seviyesi başına -4 Element Direnci",
    "content.33.359772": "Lucky Day, belirli koşullarda yükselen ve azami seviyesi 100 olan bir göstergedir.\n\nLucky Day 50'ye ulaştığında:\n[pl]Oynanan sonraki tarot kartının bedeli 1 WP azalır ve 50 Lucky Day tüketilir\n\nLucky Day 100'e ulaştığında:\n[pl]Sonraki Roll Again'in bedeli 1 AP azalır ve 100 Lucky Day tüketilir",
    "content.33.359821": "Oynanan her tarot kartının sayısal değerine göre:\n[pl][st3683] ve Kritik Vuruş bonusu (1 tur)\n\nKart oynamak artık 7 Lucky Day kazandırmaz",
    "content.33.359823": "Her tarot kartının bir rengi vardır\n\nTur başına 1 kez, art arda 2 kart oynamak şunları sağlar:\n[pl]Art arda 2 beyaz kart: [caster] [#charac WP] 1 WP\n[pl]Art arda 2 siyah kart: [caster] 25 [st3683]\n\nRoll Again artık 3 AP bedellidir",
    "content.33.360698": "Lucky Day, belirli koşullarda yükselen ve azami seviyesi 100 olan bir göstergedir.\n\nLucky Day 100'e ulaştığında:\n[pl]Çekilen sonraki kartın bedeli 1 WP azalır ve etkisi iki katına çıkar",
    "content.33.371343": "6 kart oynandığında ve [st3683] 100 değilse:\n[pl]100 Lucky Day\n[pl]Çekme destesi boşaltılır",

    # Bağlantılı durum/yetenek adları özgün WAKFU adlarıyla gösterilir.
    "content.8.950": "Unlucky Day",
    "content.8.1952": "Flame Return",
    "content.8.3129": "Invisible",
    "content.8.3303": "Exalted",
    "content.8.3600": "The Sacrificial Doll",
    "content.8.3683": "Lucky Day",
    "content.8.3882": "Sadist Mark",
    "content.8.4254": "Summoning of the Roots",
    "content.8.4840": "Flame Return",
    "content.8.5371": "Son oluşturulan rün: Incan'rune",
    "content.8.5372": "Son oluşturulan rün: Aqua'rune",
    "content.8.5373": "Son oluşturulan rün: Tellu'rune",
    "content.8.5374": "Son oluşturulan rün: Aer'rune",
    "content.8.5528": "[WILL-O'-THE-WISP] Mechanical",
    "content.8.5850": "Invisible",
    "content.8.7632": "Pressure - Incurable & Crumbly",
    "content.8.7885": "Flame Return - Counter",
    "content.8.7903": "Flame Return - Damage Bonus",
    "content.8.7917": "Sneaky",
    "content.8.7977": "Lucky Day",
    "content.8.8040": "Sneaky Blade",
    "content.8.8041": "Dagger Return",
    "content.8.8206": "Nettled Sacrificial Doll",
    "content.8.8892": "Evanescence - Sneaky",
    "content.8.8893": "Evanescence - Runaway",
    "content.8.9273": "Pressure - Incurable & Crumbly",
    "content.8.9275": "Pressure - Incurable & Crumbly",
    "content.8.9276": "Pressure - Incurable & Crumbly",
    "content.13.353693": "[se] (Flame Return tüketildi)",
    "content.13.353696": "[se] (Flame Return tüketildi)",
    "content.13.371075": "[se] (Sneaky Blade)",
    "content.13.371077": "[se] (Sneaky Blade)",
    "content.13.371205": "[se] (Dagger Return)",
    "content.13.371206": "[se] (Dagger Return)",
    "ECAFLIP_RESOURCE": "Lucky Day",
}


def source_values():
    with zipfile.ZipFile(SOURCE_JAR) as archive:
        text = archive.read("texts_en.properties").decode("utf-8-sig")
    return {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in text.splitlines()
        if "=" in line and not line.startswith(("#", "!"))
    }


def load(path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def save(path, values):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(values, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    sources = source_values()
    project = load(PROJECT)
    manual = load(MANUAL)

    # Ana dosyada bu tur elle düzeltilen kayıtları kalıcı belleğe de aktar.
    for key in (
        "content.10.302", "content.33.145442", "content.33.145838",
        "content.33.145893", "content.33.146322", "content.33.146714",
        "content.33.343275", "content.33.353795", "content.33.368130",
        "content.33.398265", "content.33.413750", "content.33.413751",
        "content.4.645", "content.4.927", "content.4.2050",
        "content.4.4671", "content.4.4683", "content.4.4720",
        "content.4.4808", "content.4.5032", "content.4.5050",
        "content.4.5124", "content.4.5463", "content.4.5577",
        "content.4.5590", "content.4.5623", "content.4.6470",
        "content.4.6471", "content.4.6909", "content.4.7054",
        "content.4.7224", "content.4.7754", "content.64.11374",
        "critere.not.isCarried", "options.playability", "content.62.2170",
    ):
        if key in project:
            manual[key] = project[key]

    normalized_fixes = {
        key: (value.replace("\n", "\\n") if "\\n" in sources.get(key, "") else value)
        for key, value in FIXES.items()
    }
    project.update(normalized_fixes)
    manual.update(normalized_fixes)

    # Haritada/zemin etkileşiminde görülen bütün gerçek "Exit" kayıtları.
    exit_keys = [key for key, source in sources.items() if source == "Exit"]
    for key in exit_keys:
        project[key] = "Çıkış"
        manual[key] = "Çıkış"

    # Eski otomatik çeviride iki kez kaçırılan satır sonlarını kaynakla eşleştir.
    normalized = 0
    for values in (project, manual):
        for key, value in list(values.items()):
            source = sources.get(key, "")
            if isinstance(value, str) and "\\\\n" in value and "\\n" in source and "\\\\n" not in source:
                values[key] = value.replace("\\\\n", "\\n")
                normalized += 1

    save(PROJECT, project)
    save(MANUAL, manual)
    print(f"FIXES={len(FIXES)} EXIT={len(exit_keys)} NORMALIZED={normalized}")


if __name__ == "__main__":
    main()
