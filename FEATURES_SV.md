# Funktioner

## Transkribering

- **Filuppladdning** - Dra och släpp eller bläddra efter ljud-/videofiler (MP3, MP4, WAV, WebM, M4A)
- **Inspelning i webbläsaren** - Spela in direkt från webbläsaren med visualisering av ljudnivå i realtid
- **Val av ljudkälla** - Välj mellan tillgängliga mikrofoner eller fånga systemljud/skrivbordsljud via skärmdelning
- **Livetranskribering** - WebSocket-baserad realtidstranskribering som strömmar segment medan du talar
- **Svensk taligenkänning** - whisper.cpp med KB-LAB:s svenska modeller, Metal GPU-accelererat på Apple Silicon
- **Automatisk ljudextrahering** - FFmpeg konverterar alla format till 16 kHz mono WAV

## Talaridentifiering

- **Pyannote.audio 3.1-diarisering** - Automatisk talarseparering med konfigurerbart min/max antal talare
- **Introduktionsbaserad identifiering** - LLM analyserar iterativt mötesinledningar för att extrahera talarnamn
- **Röstavtrycksmatchning** - SpeechBrain ECAPA-TDNN-inbäddningar med cosinuslikhet för att koppla namn till röster
- **Reservetikettering** - Talare märks som "Deltagare 1", "Deltagare 2" när inga introduktioner upptäcks
- **Livtilldelning av talare** - Provisorisk centroidbaserad talardetektering under liveinspelning
- **Poleringspass** - Efterbearbetning med sammanslagning av talare och LLM-driven namngivning

## Redigering av transkript

- **Inline-textredigering** - Klicka på ett segment för att redigera transkriptionstexten
- **Omtilldelning av talare** - Flytta segment till en annan talare
- **Namnbyte av talare** - Byt namn på vilken identifierad talare som helst
- **Anpassning av talarfärg** - Tilldela egna färger för visuell åtskillnad
- **Sammanslagning av talare** - Slå ihop två talare till en, alla segment konsolideras
- **Bevarande av originaltext** - Håller reda på original kontra redigerad text

## Ljuduppspelning

- **Synkroniserad uppspelning** - Klicka på ett segment för att hoppa till den punkten i ljudet
- **Automatisk rullning** - Transkriptet följer uppspelningspositionen automatiskt
- **Tidsstämplar** - MM:SS-tidsstämplar visas på varje segment

## Export

- **SRT** - Undertextformat med tidskoder och talaretiketter
- **WebVTT** - Webbvideoformat med rösttaggar
- **Ren text** - Talargrupperat transkript med sektionsrubriker
- **Markdown** - Formaterat med talarrubriker och tidsstämplar
- **JSON** - Strukturerad data för programmatisk användning
- **DOCX** - Microsoft Word-dokument med formaterade rubriker
- **PDF** - Professionell PDF med stilren layout och metadata

## Åtgärder (LLM-analys)

- **Anpassat åtgärdsbibliotek** - Skapa återanvändbara LLM-promptar (sammanfatta, åtgärdslista m.m.)
- **Kör mot valfritt möte** - Exekvera åtgärder på färdiga transkript
- **Resultathistorik** - Bläddra bland tidigare åtgärdsresultat per möte
- **Resultatexport** - Ladda ner åtgärdsresultat som TXT, MD, DOCX eller PDF
- **Realtidsstatus** - WebSocket-uppdateringar för pågående/färdiga/misslyckade åtgärder

## Kryptering

- **Lösenordsskydd** - Kryptera transkriptsegment med PBKDF2-nyckelderivering + Fernet-kryptering
- **Valfri kryptering av åtgärdsresultat** - Välj att även kryptera åtgärdsresultat
- **Upplåsningsflöde** - Lösenordsverifiering före dekryptering
- **Visuella indikatorer** - Låsikoner på krypterade möten

## Modellkonfiguration

- **Förinställningssystem** - JSON-baserade modellförinställningar i mappen `model_presets/`
- **Uppgiftsbaserad tilldelning** - Olika modeller för transkribering, livetranskribering, analys och åtgärder
- **Flera LLM-leverantörer** - OpenRouter (Claude Sonnet 4 m.fl.) och lokal Ollama (Qwen 3 8B, Gemma 3 m.fl.)
- **Flera Whisper-modeller** - Medium (högre kvalitet) och small (snabbare, för live) varianter
- **Inställnings-UI** - Konfigurera modelltilldelningar från webbgränssnittet
- **Beständiga inställningar** - Tilldelningar sparas i `storage/settings.json`

## Liveinspelning

- **WebSocket-strömning** - Ljudsnuttar skickas till servern var 4:e sekund som kompletta WebM-filer
- **Realtidssegment** - Transkriptionsresultat visas medan du talar
- **Inspelningsrad** - Visar förfluten tid, ljudnivåer och stoppkontroll
- **Automatisk slutbehandling** - Fullkvalitetsbearbetning startas automatiskt efter att inspelningen stoppats
- **Progressiv talarförfining** - Talarnamn förbättras i bakgrunden genom poleringspass

## Användargränssnitt

- **Mötesöversikt** - Lista över alla möten med statusmärken, längd och antal talare
- **Tre inmatningslägen** - Flikar för Ladda upp, Spela in och Live i dialogen för ny transkribering
- **Realtidsförlopp** - Steg-för-steg-förloppsindikator under bearbetning
- **Mörkt tema** - Genomgående mörkt UI i slate/violett
- **Responsiv layout** - Sidopanel med talare/åtgärder, huvudområde för transkript

## Teknik

- **FastAPI-backend** med asynkront WebSocket-stöd
- **React + TypeScript + Vite**-frontend med Zustand för tillståndshantering
- **PostgreSQL** för beständig lagring
- **Redis + Celery** för bakgrundsbearbetning
- **FFmpeg** för ljud-/videokonvertering
- **whisper.cpp** (nativ binär) för transkribering
- **pyannote.audio** för diarisering
- **SpeechBrain** för röstavtryck
