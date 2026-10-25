# Denon AVR-X2700H voor Home Assistant

Custom integratie (HACS) die de Denon AVR-X2700H volledig lokaal aanstuurt via het
**Telnet-protocol** (poort 23, push-updates). De **HTTP-API** (poort 8080) wordt alleen
gelezen voor model en MAC-adres. Bronnamen en verborgen bronnen komen live via Telnet,
dus hernoemen of verbergen op de receiver is direct zichtbaar in Home Assistant.

Wijzigingen via de afstandsbediening, het frontpaneel of de HEOS-app komen direct
binnen in Home Assistant; er wordt niet gepold.

## Installatie

1. HACS → *Integraties* → menu → *Aangepaste repositories* → voeg
   `https://github.com/bramnauta/denon-avr-x2700h-ha` toe als type *Integratie*.
2. Installeer **Denon AVR-X2700H** en herstart Home Assistant.
3. *Instellingen → Apparaten & diensten → Integratie toevoegen → Denon AVR-X2700H*,
   of bevestig de automatisch gevonden receiver (SSDP).

Handmatig: kopieer `custom_components/denon_avr_x2700h` naar `config/custom_components/`.

### Vereisten op de receiver

- **Setup → Netwerk → Netwerkbesturing: Altijd aan** (anders is Telnet niet bereikbaar
  in stand-by en kan Home Assistant de receiver niet aanzetten).
- De receiver accepteert **maar één Telnet-verbinding tegelijk**. Gebruik deze
  integratie dus niet samen met de ingebouwde `denonavr`-integratie met Telnet aan,
  en sluit eventuele andere Telnet-sessies.

## Wat zit erin

| Platform | Entiteiten |
| --- | --- |
| `media_player` | Hoofdzone (aan/uit, volume, mute, bron, surroundmodus, play/pause/stop/vorige/volgende voor HEOS/Bluetooth, tunerpresets, now-playing) en Zone 2 (aan/uit, volume, mute, bron incl. *Source*). De lijst met surroundmodi komt van de receiver zelf en past zich aan het ingangssignaal aan (bijv. *Stereo*, *Dolby Audio - Dolby Surround*, *Multi Ch Stereo*, *Direct*, *Pure Direct*) |
| `switch` | Systeemvoeding (PW), toonregeling, Cinema EQ, Dynamic EQ, LFC, dialoog-/subwooferniveau aanpassen, grafische EQ, hoofdtelefoon-EQ, Center Spread, Neural:X, Speaker Virtualizer, Loudness Management, subwoofer in Direct, Bluetooth-zender, verticaal uitrekken, instellingenmenu, All Zone Stereo, Zone 2 HPF |
| `select` | MultEQ, Dynamic Volume, referentieniveau-offset, DRC, audio restorer, dialoogversterker, ingangsmodus, digitale decodering, ECO, auto stand-by, dimmer, luidsprekerpreset, Bluetooth-uitvoer (BT + luidsprekers / alleen BT), beeldverhouding, beeldmodus, videoresolutie, HDMI-resolutie, HDMI-audio-uitgang, videoverwerking, tunerband/-modus, Zone 2 kanaalinstelling en auto stand-by |
| `number` | Volume in dB, lage/hoge tonen, dialoogniveau, subwooferniveau (1 en 2), LFE-niveau, audiovertraging, LFC containment, slaaptimer, tunerpreset, kanaalniveaus per aangesloten luidspreker, Zone 2 volume/tonen/kanaalniveaus/slaaptimer |
| `sensor` | Surroundmodus (code, bijv. `DOLBY AUDIO-DSUR`, en leesbaar, bijv. *Dolby Audio - Dolby Surround*), audioformaat (bijv. PCM), ingangskanalen, samplefrequentie, ingangssignaal, volumelimiet, tunerfrequentie en -zender. Diagnostisch: luidsprekeropstelling (grootte per positie, aantal surround back, subwoofer), crossovers, afstanden en gekalibreerde niveaus per aangesloten luidspreker |
| `button` | Menunavigatie (cursor, enter, terug, optie, info), Quick Select 1–4 (hoofdzone en Zone 2), tuner preset/frequentie omhoog/omlaag, kanaalniveaus resetten, volgende/vorige surroundmodus, status verversen, frontpaneel/afstandsbediening (ont)grendelen (standaard uitgeschakeld) |

Standaard uitgeschakeld (aan te zetten in het entiteitenregister): effectniveau, monitoruitgang,
videoselectie, beeldmodus en de vergrendelknoppen. De vergrendeling kan de receiver niet
terugmelden, daarom zijn het knoppen en geen switches. Let op: met *Afstandsbediening
vergrendelen* werkt de IR-afstandsbediening niet meer tot je *Afstandsbediening ontgrendelen*
indrukt.

Entiteiten worden pas aangemaakt zodra de receiver een waarde voor die instelling
meldt. Instellingen die bij jouw luidsprekeropstelling of firmware niet bestaan (bijv.
ongebruikte kanalen of Subwoofer 2) verschijnen dus niet. Sommige audio-instellingen
worden pas gemeld als de hoofdzone aan staat of in een bepaalde surroundmodus.

### Services

Alle services richten zich op een media player van deze integratie.

- `denon_avr_x2700h.send_command` — stuur willekeurige Telnet-commando's
  (bijv. `PSDYNEQ ON`, `MV?`, `SYREMOTE LOCK ON`) en krijg de antwoorden terug
  als service-response. Hiermee is ook alles bereikbaar wat niet als entiteit bestaat.
- `denon_avr_x2700h.save_quick_select` — huidige instellingen opslaan in Quick Select 1–4.
- `denon_avr_x2700h.set_tuner_frequency` — FM in MHz (`101.2`) of AM in kHz (`747`).
- `denon_avr_x2700h.refresh` — alle statuswaarden opnieuw uitlezen.

Voorbeeld:

```yaml
action: denon_avr_x2700h.send_command
target:
  entity_id: media_player.denon_avr_x2700h
data:
  command:
    - "PSDELAY ?"
    - "SSINFAISFSV ?"
response_variable: antwoord
```

### Opties

- **Zone 2 inschakelen** (standaard aan)
- **Volume bij 100%** — welke dB-waarde de volumeschuif van de media player op 100%
  zet (standaard 0 dB, zodat een slider-ongelukje niet op +18 dB eindigt). Staat op de
  receiver een lagere volumelimiet ingesteld, dan geldt die (bijv. −20 dB).
  De `Volume`-number-entiteit kan wel het volledige bereik −80…+18 dB.
- **Volumestap** voor volume omhoog/omlaag (standaard 0,5 dB).

## Buiten scope

- **HEOS** (streamingdiensten, favorieten, multiroom, albumhoezen) loopt via het aparte
  HEOS-CLI-protocol op poort 1255. Gebruik daarvoor de ingebouwde **HEOS**-integratie van
  Home Assistant; die werkt naast deze integratie.
- Instellingen die alleen in het on-screen setup-menu zitten en niet via Telnet
  beschikbaar zijn (luidsprekerconfiguratie, Audyssey-meting, netwerkinstellingen).

## Ontwikkeling

```bash
pip install pytest aiohttp
pytest --ignore tests/test_init.py
python scripts/gen_translations.py   # na wijzigingen in protocol.py
```

De end-to-end test in Home Assistant (`tests/test_init.py`) draait alleen op Linux/macOS
(of in Docker/CI), niet op Windows:

```bash
pip install pytest-homeassistant-custom-component
pytest tests/test_init.py -o asyncio_mode=auto
```

`protocol.py` (commandotabel en conversies) en `client.py` (Telnet-verbinding) hebben
geen Home Assistant-afhankelijkheden en worden getest tegen een nagebootste receiver.
Nieuwe instellingen voeg je toe als regel in `SETTINGS` in `protocol.py`, plus een
naam in `scripts/gen_translations.py`.
