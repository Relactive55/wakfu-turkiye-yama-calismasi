WAKFU TÜRKÇE ÇEVİRİ ARACI

Güncel sürüm: 29.08-WakfuQuality-v43-Portable
Ana klasör: bu temiz depo klasörü

KULLANIM
1. Wakfu_Turkce_Ceviri_Araci.exe dosyasını açın.
2. Arama kutusunda anahtar, İngilizce metin veya Türkçe metin arayabilirsiniz.
3. Bir satırı seçip sağ alttaki Türkçe alanından elle düzeltebilirsiniz.
4. Değişiklikler kısa bir gecikmeyle güvenli biçimde kaydedilir. Hemen yazmak için Ctrl+S veya Kaydet düğmesini kullanın.
5. Baş üstü yazı boyutunu Normal, Küçük (önerilen) veya Çok küçük olarak seçin. Oyuna Kur düğmesi güncel Türkçe i18n.jar, font ve istemci paketlerini bu seçimle WAKFU klasörüne kurar.
6. Orijinali Yedekle temiz oyun dosyalarını saklar; Orijinali Geri Yükle bu temiz dosyalara döner.
7. Oyun güncellenirse program i18n_en.jar, gui.jar ve istemci dosyasındaki değişikliği algılar, yeni temiz kaynakları projeye alır ve kullanıcıya güncelleme bulunduğunu bildirir.
8. ÇEVİRİ düğmesi yalnız eksik veya kalite denetiminden geçmeyen metinleri yerel NVIDIA GPU ile işler. GPU ortamı yoksa depo kökündeki `GPU` klasörü veya `WAKFU_GPU_RUNTIME` yolu kullanılabilir.

KLASÖRLER
- Kaynak_Kodu: Program, kurulum, paketleme ve GPU kaynak kodları.
- Ceviri_Verileri: Tek geçerli ana çeviri, manuel onarım, terim ve GPU bağlam JSON'ları.
- Oyun_Kaynaklari\Guncel: Oyundan alınan güncel temiz kaynaklar.
- Oyun_Kaynaklari\Orijinal_Yedek: Geri dönüş için temiz oyun dosyaları.
- Oyun_Kaynaklari\Fontlar: Türkçe karakter fontları.
- Oyun_Kaynaklari\Yamalar: i18n dışında, çalışma zamanında gelen metinler için doğrulanmış istemci yamaları.
- Ayarlar: Arayüz ayarı, GPU yolu ve paket önbelleği.
- Uretilenler: Oyuna kurulmaya hazır JAR dosyaları.
- Raporlar: Tam kalite, canlı işlem, hata ve arayüz test raporları.
- Belgeler: Kullanım ve proje bilgileri.
- Araclar: Tam denetim ve paket üretimi için proje içindeki bağımsız Python çalışma ortamı.

GÜNCEL KALİTE DURUMU - 29.08.2026
- Kaynak oyun metni: 154.963.
- Doğrulanmış çeviri: 97.436.
- Bilinçli korunan ad: 37.699.
- Bilinçli korunan teknik metin: 19.828.
- Eksik çeviri: 0.
- Tamamen İngilizce kalan: 0.
- İngilizce kalıntısı bulunan: 0.
- Biçim/yer tutucu hatası: 0.
- Ana çeviri JSON'u: 100.344 anahtar.
- Manuel onarım belleği: 89.863 anahtar.

Son insan denetimli gruplar Parti 217'ye kadar uygulandı. Parti 178-217 çalışması; i18n metin düzeltmelerini, özgün kalacak beceri/eşya adlarını, Türkçeleştirilecek görev ve başarım metinlerini, hava durumu saat biçimini, V oyuncu adı görünürlüğünü ve HAAPI üzerinden gelen Talentyre ile Dyw Almanax açıklamalarının güvenli istemci yamalarını kapsar. Bütün büyü/yetenek ve eşya başlıkları özgün İngilizce adıyla korunur; görev başlığı gibi farklı bağlamlarda kullanılan aynı metinler ise bağlama göre Türkçeleştirilir. Emote araç ipuçlarındaki slash komutları aynen korunur. Uretilenler\i18n.jar ve bütün dağıtım paketleri bu verilerle yeniden oluşturuldu; istemci sınıfları gerçek Java üzerinde doğrulandı.

Güncel kalite denetiminde incelenmesi gereken kayıt kalmamıştır. Korunan ad ve teknik metinler hata değil, oyun uyumluluğu için bilinçli sınıflardır. Program, biçimi güvensiz olan bir çeviriyi oyuna yazmak yerine İngilizce kaynağı korur. Ayrıntılar Raporlar\Wakfu_Ceviri_Ozet.txt ve Raporlar\Wakfu_Ceviri_Sorunlar.tsv dosyalarındadır.

ÖNEMLİ
- [#1], {…}, <b>…</b>, [pl], [st…] ve \n gibi oyun işaretlerini silmeyin veya değiştirmeyin.
- Oyuna kurulum ve geri yükleme sırasında WAKFU ile Ankama Launcher kapalı olsun.
- Düzenleme için yalnız Ceviri_Verileri klasöründeki dosyaları kullanın; AppData veya eski Codex çıktılarında ikinci kopya oluşturmayın.
- Program EXE'si ana klasördeyken doğrudan bu düzenli proje yapısını kullanır.
- Baş üstü boyut seçimi yalnız V ile gösterilen oyuncu/NPC adı ve altındaki unvan satırını etkiler; sohbet ve diğer arayüz metinleri değişmez. Seçim kaydedilir ve farklı bir boyut seçildikten sonra Oyuna Kur ile yeniden uygulanabilir.
