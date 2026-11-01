# Stil rehberi: "çöp adam hikâye anlatımı" (kaynak: 3 kare analizi)

Not: Bu rehber yalnızca 3 durağan kareden çıkarıldı. Hareket (animasyon) kısmı **çıkarım**dır; kaynak videoyu izleyince güncelle.

## 1. Biçim
- Dikey 9:16 (kareler ≈ 0.578 oran). Üretim: 1080×1920, 30 fps. Reels/Shorts/TikTok.
- Bir sahne = bir cümle = bir fikir. Sahne başına 2.5–4 sn, altyazı en fazla ~6 kelime.
- Platform arayüzüne denk gelen kenar bölgeleri önemli ögeyle doldurma (güvenli alan).

## 2. Palet (karelerden örneklendi)
| Rol | Hex | Kullanım |
|---|---|---|
| Kâğıt | `#f3ebdd` | Zemin; kenarlara doğru `#e3dccb` vinyet + hafif tane (grain) |
| Mürekkep | `#2b2723` | Karakter, zemin çizgisi, nesne konturları |
| Vurgu (kırmızı, kiremit tonu) | `#b8372d` | Konuşulan anda vurgulanan kelime, **vurgulu kelime**, "yok/hayır" çarpıları |
| Güneş | `#d89d48` | Sadece güneş (kontur + yumuşak ışıma) |
| Metin | `#2e2821` | Altyazı gövdesi |
| Soluk gri | `#6a645a` | Alt başlık |

Not: Referans videoda vurgu petrol mavisiydi (`#346072`); bu skill'de vurgu rengi kırmızıdır. Değiştirmek için `meta.palette.accent` yeterli.

Kural: vurgu rengi **anlam taşır** (özne / kilit kelime / olumsuzlama). Dekor için kullanma. Ekranda tek vurgu rengi + güneş sarısı yeter.

## 3. Karakter
- Kafa: dolu siyah, hafif düzensiz daire. Yüz kâğıt renginde: nötr = 2 nokta göz + kısa çizgi ağız; mutlu = kapalı göz kavisleri + gülümseme.
- Gövde/uzuv: ince, "örgülü" çift vuruşlu çizgi (≈ 11–12 px). Kâğıt hissi için çizgi titremesi (line boil, ~8 fps).
- Figür varsayılan olarak aksesuarsızdır. Miğfer, taç, şapka veya pelerin eklemek için anlatıda açık bir neden ya da kullanıcı isteği olmalı. Tarihî kişilere yalnızca adlarından yola çıkarak kostüm uydurma; özellikle İskender'in başına/kıyafetine otomatik kırmızı miğfer, pelerin ya da başka kırmızı parça ekleme.
- Vurgu rengini karakter kimliği veya kıyafet rengi gibi kullanma. Kırmızıyı yalnızca anlatıdaki anlamlı vurgu için kullan: o anda söylenen altyazı sözcüğü, gerektiğinde statik anahtar sözcük veya olumsuzlama işareti.
- Ölçek hiyerarşisi: güç/statü = **ayakta ve uzun**; sade/özgür = **oturan ve küçük**. (Kare 2: İskender ayakta hayal kurar, Diyojen yere oturmuş.) Hikâyedeki ironi kompozisyonla anlatılır.

## 4. Kompozisyon ilkeleri (sabit koordinat yok — her video için yeniden kur)
- Zemin çizgisi kullanılacaksa tek, dalgalı, uçları hafif kalın bir çizgi; yeri sahneye göre seçilir. Konu zemin gerektirmiyorsa hiç kullanma.
- Altyazı: ortalı, sade sans-serif, kilit kelime kalın + vurgu rengi. Platform arayüzüyle çakışmayacak, sahne ögeleriyle yarışmayacak bir yere konur.
- Başlık kartı (gerekirse): serif büyük harf, geniş harf aralığı, çift kaba çizgi, altında küçük gri büyük harf alt başlık. Boyutlar başlığın uzunluğuna göre ayarlanır.
- Güneş (veya başka bir süreklilik motifi) sahneler arası tutarlılık için kullanılabilir; yeri ve boyutu sahneden sahneye anlamlı biçimde değişebilir (ör. büyüyerek zamanın geçişini gösterir). Konuya uymuyorsa atla.
- Asimetri ve bol negatif alan tercih edilir; ana özne baskın, yan ögeler küçük.
- Düşünce balonu: karakterin kafasına iki küçük daireyle bağlanır; içeriği küçük ölçekli sahne.
- Bilgi şeridi (ikon dizisi): eşit aralıklı basit ikonlar; "yok/hayır" olanlar vurgu renginde X ile çizilir, kalanlar çarpısız.
- Ölçek, sayı ve konum içeriğe bağlıdır: önce sahnenin tek fikrini seç, düzeni ona göre kur.
- Düğüm gibi karmaşık bir nesneyi karikatürize ama seçilebilir çiz: birkaç kalın, kesişen ilmek; üstten/ alttan geçişi ayıran küçük boşluklar; belirgin sıkı merkez ve görünen ip uçları. Karışık çizgi yumağı gibi görünmesine izin verme.
- Kılıcın siluetinde kabza, el koruması ve sivri namlu seçilsin. Kesilme sonrasında ip iki ayrı uca bölünsün; uçların arasında görünür boşluk bırak ve kesilmiş yüzleri kılıcın hareket yönüyle ilişkilendir. Bu ayrıntıyı küçük parıltı veya hareket çizgileriyle destekleyebilirsin; kılıcın/düğümün okunaklılığını azaltma.
- Sesli anlatım varsa kelime vurgusunu cümle boyunca hareket ettir: o anda söylenen sözcük vurgu kırmızısı, diğer sözcükler normal metin renginde olsun. `karaoke` aralıkları sahne başlangıcına göre saniye cinsindendir ve altyazıdaki boşlukla ayrılmış her sözcük için bir aralık bulunur. Geçişleri ses zamanlamasına oturt; sahne boyunca sabit kırmızı bir kelime bırakma.

## 5. Hareket (çıkarım — doğrulanmadı)
- Zemin çizgisi soldan sağa çizilir (wipe), sonra güneş yumuşak belirir, başlık hafif yükselerek gelir.
- Karakter "pop" (hafif aşağıdan yukarı + fade). Altyazı en son, 20–25 px yükselerek.
- İkonlar sırayla, ~0.5 sn arayla; X çarpıları ikondan hemen sonra.
- Sahne geçişi: sert kesme ya da ≤0.2 sn çapraz geçiş. Arka plan sahneler arasında **değişmez**.
- Ses: anlatıcı + sakin piyano/ambient müzik; altyazı seslendirmeyle senkron (cümle başına sahne).

## 6. Anlatı kalıbı (kare dizisinden)
1. Başlık kartı + tek cümlelik tanım ("Büyük İskender'di.")
2. Kanca/çatışma ("İskender olmasaydım…" — hayal balonuyla karşı karakter)
3. Karşı karakterin özünü gösteren somut liste ("…ve bir kâseydi.")
Her sahnede **yeni tek bilgi**; bilgi bir önceki sahnedeki görselin üstüne eklenir. Sahneler arası süreklilik için karakter, zemin ve motifler `carry` ile taşınır: ana karakter sahneden sahneye aynı çizimle kalır, yalnızca yer/ifade değişir; artık gereksiz olanlar `until` ile sönerek çıkar. Sahne başına değişen şey azdır, bu da izleyicinin tek yeni bilgiye odaklanmasını sağlar.

## 7. Yapma listesi
- Gradyan/gölge/3B yok. Düz renk + kontur.
- Bir sahnede 2'den fazla karakter yok, 5'ten fazla ikon yok.
- Altyazıyı 2 satırdan uzatma; uzun cümleyi iki sahneye böl.
- Vurgu rengini bir sahnede 2 kelimeden fazlasına verme.
- Anlatı veya kullanıcı isteği gerektirmedikçe karaktere kırmızı aksesuar/kostüm ekleme.
- Kelime zamanları verilmiş anlatıda vurgu rengini sabit bir kelimede tutma; aktif sözcük sesle birlikte ilerlemeli.
- Düğümü gelişigüzel karalama gibi, kılıcı tanınmaz bir çizgi gibi veya kesilmiş ipi hâlâ bitişik çizme.

