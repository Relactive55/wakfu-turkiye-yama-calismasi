# Güvenlik ve dağıtım

## Dağıtım ilkesi

- Kullanıcıya sunulan kurulum EXE'si, Türkçe yama paketleri ve doğrulama dosyaları yalnızca bu deponun GitHub Releases varlıklarında yayımlanır.
- README, dokümantasyon, iş akışları ve proje metadatasında harici dosya barındırıcılarına, kısaltılmış bağlantılara veya yönlendirme servislerine ait dağıtım bağlantıları kullanılmaz.
- Otomatik çeviri doğrulamasında kullanılan Argos modeli, bu depodaki hash kilitli GitHub Release varlığından alınır; boyut ve SHA-256 doğrulanmadan kullanılmaz.
- Güncel WAKFU kaynak dosyası yalnızca resmi Ankama CDN uç noktasından, yönlendirmeler reddedilerek ve bütünlük doğrulaması yapılarak alınır. Bu, kullanıcı dağıtımı değildir.

## Çeviri sağlayıcısı kullanılamadığında

- Argos modeli yalnızca bu depodaki hash kilitli GitHub Release varlığından alınır; çalışma ortamı, Release varlığı veya doğrulama verisi eksikse iş akışı güvenli biçimde durur.
- Bu durumda çeviri belleği, durum dosyası, dal, PR ve Release yazılmaz. Yalnızca tekilleştirilmiş bir bekleyen-sağlayıcı bildirimi açılır; mevcut onaylı bellek ve sözlük korunur.
- Yeni veya değişen satırlar güvenilir yerel GPU aracı ya da manuel incelemeyle onaylandıktan sonra belleğe eklenir. Sonraki otomatik çalışma aynı manuel/bellek/sözlük önceliklerini kullanır.
- Kullanıcıya sunulan dağıtımda alternatif veya harici bir makine çevirisi servisine sessizce geçiş yapılmaz; bu, güvenlik ve kalite kurallarını korumak için kasıtlıdır.

## Bildirim

Şüpheli bir dosya, bağlantı veya davranış görürseniz bu depoda yeni bir güvenlik bildirimi açın ve ilgili dosya yolu ile gözleminizi ekleyin. Bildirimde parola, erişim belirteci veya kişisel bilgi paylaşmayın.
