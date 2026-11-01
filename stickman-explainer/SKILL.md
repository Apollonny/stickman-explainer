---
name: stickman-explainer
description: Produce short vertical (9:16) hand-drawn stick-figure explainer/story videos (Instagram Reels / Shorts / TikTok history & anecdote style) from a script, using a Python renderer driven by a JSON storyboard. Cream paper background, black-ink stick figures, one red accent colour, optional sun motif, and captions whose red emphasis follows the spoken word when word timings are supplied. Use whenever the user wants an animated explainer, stickman video, "çöp adam" animasyon, kısa hikâye/tarih/anekdot videosu, or asks to automate this kind of video with an AI coding agent — even if they only say "make a video like this reel".
compatibility: Python 3.9+, Pillow, numpy, ffmpeg on PATH. Fonts Poppins + Lora/Playfair Display (OFL, Google Fonts). Works in any coding agent (Claude Code, Codex CLI, OpenCode, Antigravity).
---

# stickman-explainer

Turns a short script into a finished 1080×1920 mp4. You write a **storyboard JSON**; `scripts/render.py` draws every frame (wobbly ink lines, line-boil at 8 fps, fade/wipe/pop reveals) and encodes with ffmpeg.

`assets/example_storyboard.json` yalnızca **söz dizimi örneğidir** (3 sahne); yerleşimini veya karakter aksesuarlarını şablon olarak kopyalama.

## Visual style defaults

- Use a 9:16 canvas (1080×1920, 30 fps). Keep each scene to one idea, usually 2.5–4 seconds, with short captions inside platform-safe areas.
- Use warm paper (`#f3ebdd`), dark ink (`#2b2723`), and semantic brick-red accent (`#b8372d`). Sun gold (`#d89d48`) is optional for the sun motif only. Keep the rest flat: no gradients, shadows, or 3D effects.
- Draw simple black-ink figures with clear faces and plenty of negative space. Do not add helmets, crowns, capes, red clothing, or other accessories unless the story or user asks for them. Do not infer costumes from a historical name.
- Keep scenes readable: at most 2 characters and 5 small icons. Make the main subject dominant; avoid captions and props overlapping. Use no more than 2 caption lines.
- Make complex props recognizable. Draw a knot with distinct crossing loops, a tight center, and visible rope ends. Give a sword a clear grip, guard, and pointed blade. After a cut, leave a visible gap between the two rope ends.
- When narration timings are available, make the red caption emphasis follow the currently spoken word throughout the narration. Use a `karaoke` interval for every whitespace-separated caption word; non-active words remain in the normal text colour.
- Prefer asymmetrical layouts and leave deliberate negative space. Ground lines, suns, title cards, thought bubbles, and other motifs are optional; choose them only when they support the scene.

## Workflow

1. **Script → scenes.** Split the story into one-sentence scenes (≤ 6 words of caption, 2.5–4 s each). Pattern: title card → hook/conflict → concrete reveal. Each scene adds exactly one new piece of information. When narration is supplied, align scene boundaries to the spoken sentences.
2. **Pick a visual for each sentence.** One metaphor per scene: character + prop, thought bubble, or a row of icons (X = "does not have"). Keep ≤ 2 characters and ≤ 5 icons.
3. **Write the storyboard** (schema below). With word-level narration timings, add one `karaoke` interval for every whitespace-separated caption word so the red accent follows the word being spoken. Use `**word**` only for a static highlight when word timing is unavailable; do not combine static markup with `karaoke`.
4. **Check stills first** (fast, ~2 s/scene):
   `python scripts/render.py story.json --stills out/stills` → open each `scene_NN.png`, fix overlap/placement, repeat.
5. **Draft video:** `python scripts/render.py story.json out/draft.mp4 --draft` (no supersampling, 12 fps).
6. **Final:** `python scripts/render.py story.json out/final.mp4 [--audio voiceover.mp3]`.
   Scene durations should match the voiceover sentence lengths; measure audio with `ffprobe` and set `duration` accordingly. Word intervals are seconds from the start of their scene and should come from narration alignment or careful listening. Check that each red word appears with its spoken audio, not ahead of or behind it.

## Hata mesajları ve doğrulama
`render.py` storyboard'u çizmeden önce doğrular: bilinmeyen `type`/`pose`/`face`/`kind`/`font`, eksik zorunlu alan, aynı sahnede tekrarlanan `id`, `duration <= 0`, tek noktalı `lines` yolu, tek sayılı (çift olmayan) çözünürlük ve olmayan `carry` id'si **traceback yerine açık mesajla** reddedilir. Hiçbir zaman görünmeyecek ögeler (sahne bitişinden sonraki `at`) için uyarı verilir. Ses dosyası videodan kısaysa sonu sessizlikle doldurulur, uzunsa kesilir; video süresi **asla** değişmez.

## Storyboard schema

```json
{"meta": {"width":1080,"height":1920,"fps":30,"boil_fps":8,"transition":0.18,
          "palette":{"accent":"#b8372d"}, "audio":null, "font_dirs":[]},
 "scenes":[{"duration":3.4, "caption":"Büyük **İskender**'di.",
            "caption_at":0.5, "caption_y":null, "elements":[ ... ]}]}
```

For speech-following word emphasis, provide a `karaoke` array with one `{ "start": seconds, "end": seconds }` object per whitespace-separated word in `caption`. Times are local to the scene; the red emphasis switches at each interval. The caption must not contain `**...**` markup when `karaoke` is present.

```json
{"duration":2.8, "caption":"Düğümü tek hamlede kesti.", "caption_at":0.35,
 "karaoke":[{"start":0.35,"end":0.76},{"start":0.76,"end":1.02},
            {"start":1.02,"end":1.53},{"start":1.53,"end":2.15}],
 "elements":[ ... ]}
```

Every element: `type`, optional `id` (carry için), `at` (s, appear time), `dur` (reveal s), `anim` = `fade` | `wipe` | `rise` | `pop`, `until`/`out_dur` (sönme).
Positions `x`,`x2`,`y`,`ground` ≤ 2 are read as fractions of width/height, otherwise pixels. Sizes are always pixels.

| type | key fields |
|---|---|
| `ground` | `y` (zorunlu); `x`, `x2` isteğe bağlı, verilmezse tuvalin ~%2–%98'i — wobbly baseline |
| `sun` | `x`,`y`,`r`,`rays` |
| `text` | `text` (`**accent**` markup), `x`,`y`,`size`,`font` = sans/sans_bold/sans_light/serif, `tracking`, `caps`, `color`, `max_w`, `max_lines` (varsayılan 3), `rules` (başlık kartı için çift çizgi; genişliği ve aralığı metne göre otomatik) |
| `figure` | `x`,`ground`,`h`,`head_r`, `pose` = stand/arms_open/point/wave/think/shrug/sit, `dir` (±1), `face` = neutral/smile/sad/surprised/angry, optional `accessory` = helmet/crown/hat/glasses, optional `cape`, `look` |
| `prop` | `kind` = barrel/bowl/bucket/house/book/box/triangle/coins/tree, `x`,`y` (top-left), `w`,`h`, `cross` (accent X), `flip` |
| `thought` | `x`,`y`,`w`,`h`, `tail_to` [px,py] (head position), `inner`: list of elements in bubble-local px |
| `lines` | `paths` (list of point lists, local px), `closed`, `smooth`, `color`, `width` — escape hatch for any custom shape |

### Sahneler arası süreklilik (carry)
Bir sahnenin ögesini sonraki sahneye taşımak için ögeye `id` ver, sonraki sahnede `carry` ile çağır. Taşınan öge **aynı çizgi titreşimiyle** (aynı seed) başlar, yani sahne değişse bile "aynı çizim" olarak görünür; yeni sahne geçişi varsayılan olarak kesmedir (çapraz geçiş yok).

```json
"carry": [
  "ground",
  {"id": "sun",  "set": {"r": 122}},
  {"id": "alex", "set": {"x": 120, "face": "smile"}, "tween": {"at": 0.1, "dur": 0.9}},
  {"id": "diog", "until": 0.1, "out_dur": 0.5}
]
```
Satırlar sırayla: `"ground"` aynen taşınır · `sun` alan değiştirilerek taşınır (değişiklik sahne başında anında olur) · `alex` hem alan değiştirir hem konumu süre boyunca kayar (`tween`) · `diog` taşınır ama sahne içinde sönerek çıkar.
- `"carry": "all"` her şeyi taşır (`"carry_except": ["id", ...]` hariç tutar). Altyazı asla taşınmaz.
- Taşınmayan öge sahne başında anında kaybolur; yumuşak kaybolması için `until`/`out_dur` kullan. `until` ile sönen öge sonraki sahneye taşınamaz.
- `tween` yalnızca **konum** (x ve y/ground) animasyonlar; boyut (`r`, `h`, `w`) ve görünüm (`face`, `pose`) değişimleri sahne başında anında uygulanır.
- Taşınan ögeler yeni ögelerin **altında** çizilir. Taşınacak ögeler için sahneler arası `id` benzersiz olmalı.
- Aynı `id`'li öge her sahnede aynı seed'i kullanır; sahneye özgü yeni öge için `id` verme.

Add new props/poses by extending `PROPS` / `hands` in `render.py`; keep the same ink style (use `stroke()`, never plain lines).

## Layout: her video için yeniden karar ver
Sabit koordinat/şablon yok. Her videonun konusu farklı olduğu için yerleşimi sahnenin içeriğinden türet:
- Önce o cümlenin **tek görsel fikrini** seç (karşılaştırma, liste, hayal, yolculuk, sayı…), sonra ona uyan düzeni kur. Aynı videoda sahneler arasında düzen değişebilir.
- Önemli olan ögeye yer aç: ana özne en büyük/en belirgin olsun; yan ögeler küçük kalsın. Boş alan (negatif alan) bilinçli bırakılsın.
- Büyüklük, konum ve sayı içeriğe göre değişir (1 karakter mi, 2 mi; ikon şeridi mi, tek büyük nesne mi, harita/zaman çizgisi mi). Gerekirse `lines` ile özel şekil çiz.
- Tarihî kişilere otomatik kostüm/başlık ekleme. Figürler varsayılan olarak aksesuarsız çizilir; miğfer, taç, şapka veya pelerin yalnızca anlatı ya da kullanıcı açıkça gerektiriyorsa eklenir. Vurgu rengini karakterin kıyafetine dekor olarak yayma.
- Düğüm ve kesme sahnelerinde nesneyi okunaklı kur: ipi belirgin biçimde üst üste geçen birkaç ilmekle çiz, merkezde sıkı düğüm göster ve ip uçlarını ayırt et. Kılıçta kabza, el koruması ve sivri namlu seçilebilsin. Kesme anından sonra iki kesik ip ucunu aralıklı ve açıkça görünür bırak; kılıç ve düğüm altyazı tarafından kapatılmasın. Özel ip/kılıç şekillerini `lines` ile çiz.
- Zemin çizgisi, güneş, başlık kartı gibi motifler **isteğe bağlıdır**; konuya uymuyorsa kullanma (ör. iç mekân, gece, soyut kavram).
- Altyazıyı okunur ve platform arayüzünden uzak bir yere koy; çakışırsa `caption_y` ile oynat. Çakışma ve taşmayı **still'lerde gözle kontrol et**, sayıya güvenme.
- Çizim koordinatları 1080×1920 tuvalde piksel (veya 0–2 arası oran) olarak verilir; değerleri her sahne için sıfırdan planla.

## Gotchas
- Always view stills before encoding; overlapping elements and clipped sun rays are the usual defects. Taslak için `--draft`, ayrıntı için tam render: değişmeyen kareler yeniden çizilmez, 10 sn'lik video tam kalitede yaklaşık 20 sn sürer.
- Altyazı 86 % genişliğe kadar satır kaydırır (en fazla 3 satır), ancak bir kelime sığmazsa ya da 3 satırı aşarsa küçülür. 2 satırı geçen cümleyi iki sahneye böl. Varsayılan altyazı konumu yalnızca yedektir; gerekirse sahnede `caption_y` ver.
- Fonts: Poppins ve Playfair Display (veya Lora) kur ya da `--font-dir` ver. Hiç TrueType font bulunamazsa renderer **uyarı basar** ve Türkçe karakterler (İ ş ğ â) eksik çıkabilir; still'lerde kontrol et. Linux, macOS ve Windows font klasörleri taranır.
- Keep the accent colour semantic (subject, keyword, negation). Don't add more colours.
- When `karaoke` is present, the red caption emphasis follows the narration word by word using the supplied intervals. Do not leave a fixed red keyword on screen; render non-active words in the caption text colour.

