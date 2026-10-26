# Smart Greenhouse

Webapp leggera per sviluppare sul PC e controllare una serra con Raspberry Pi 3 Model B. Python 3.10+, Flask, HTML/CSS/JavaScript vanilla, SQLite. Nessun Node.js, Docker, servizio cloud o asset esterno. Interfaccia in italiano, utilizzabile anche su touchscreen da 800 × 480 con scorrimento verticale.

**Il progetto è locale. La configurazione predefinita usa soltanto hardware virtuale e ascolta su `127.0.0.1:5000`. Nessuna libreria GPIO è necessaria sul PC.**

## Avvio sul PC Windows

Apri PowerShell nella cartella di progetto:

```powershell
python -m venv .venv                 # solo se non esiste già
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
```

Apri **http://localhost:5000**. Dopo l'installazione basta l'ultimo comando. In alternativa `powershell -ExecutionPolicy Bypass -File .\start.ps1` prepara le dipendenze mancanti e avvia il server; il Bypass vale soltanto per quel processo. Non è necessario attivare l'ambiente virtuale o cambiare la policy del PC. Arresta con `Ctrl+C`.

Su Linux/macOS usa `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements-dev.txt` e `.venv/bin/python app.py`. Non usare `flask run`, il reloader o più worker: il controllo hardware deve avere un solo proprietario.

Il server usa Waitress anche in locale, senza debugger. Non vengono eseguiti comandi specifici del Raspberry sul PC. La prima versione è stata verificata su Windows/Python 3.12 con dipendenze elencate in `requirements-local.lock.txt`; quest'ultimo è il riferimento dell'ambiente di test, mentre `requirements.txt` è la lista portabile di dipendenze runtime.

## Cosa puoi provare subito

1. Premi **Accendi / Spegni** in modalità manuale: lo stato arriva dalla risposta del server.
2. Modifica gli orari e premi **Salva orari**. Cambiano anche la durata giornaliera e la barra delle 24 ore.
3. Seleziona **Automatica**: la lampada assume immediatamente lo stato previsto dalla fascia salvata. Il pulsante manuale viene disabilitato.
4. Salva una fascia come `22:00 → 06:00`: l'accensione attraversa la mezzanotte.
5. Chiudi il browser lasciando Python in esecuzione: lo scheduler continua a lavorare. Riapri la dashboard per verificare lo stato.
6. Riavvia il server: modalità e orari rimangono salvati; l'accensione manuale riparte sempre spenta. In automatico viene ricalcolata la fascia corrente.

Le letture **24,6 °C** e **62%** sono esempi fissi e mostrano esplicitamente **Simulato**. Non sono una simulazione termica. In modalità `real`, senza sensori implementati e collegati, l'API restituisce `null` e la dashboard mostra **Non disponibile**.

I comandi aggiornano subito l'interfaccia; il polling ogni 3 secondi sincronizza anche gli altri browser. Quando il server non risponde, i comandi vengono disabilitati e i valori vengono indicati come non disponibili. Il browser riprova automaticamente. Un comando andato in timeout non viene ritentato alla cieca: il client rilegge prima lo stato.

## Configurazione

Copia `.env.example` in `.env` se vuoi personalizzare il comportamento. Le variabili d'ambiente hanno precedenza sul file. I percorsi relativi sono risolti dalla cartella del progetto, non dalla cartella del terminale.

| Variabile | Valore iniziale | Significato |
| --- | --- | --- |
| `HARDWARE_MODE` | `mock` | `mock` o `real`; un valore invalido blocca l'avvio |
| `NETWORK_MODE` | `local` | `local`: solo loopback; `lan`: tutte le interfacce IPv4 |
| `PORT` | `5000` | Porta TCP da 1024 a 65535 |
| `TIMEZONE` | `Europe/Rome` | Fuso IANA usato anche su Windows grazie a `tzdata` |
| `DATA_DIR` | `data` | Directory per SQLite e lock del processo |
| `RELAY_PIN` | `17` in mock | Numero **BCM**, obbligatorio esplicitamente in `real` |
| `RELAY_ACTIVE_HIGH` | `false` in mock | `true` oppure `false`, obbligatorio esplicitamente in `real` |
| `API_TOKEN` | vuoto | In LAN almeno 32 caratteri casuali |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | IP e nomi ammessi nell'header Host, senza porta, URL o wildcard |

Pin e polarità si modificano a servizio arrestato e richiedono un riavvio. Non si cambiano da una richiesta web, per evitare di azionare il pin sbagliato durante una riconfigurazione. La dashboard ne mostra la configurazione.

SQLite usa transazioni atomiche. Un database danneggiato o una configurazione invalida bloccano l'avvio: non vengono sovrascritti con valori di default. Per il backup, arresta il server e copia `data/greenhouse.sqlite3`. Conserva i backup separatamente. `data/` e `.env` sono esclusi dall'archivio di distribuzione e da Git.

## Programmazione e comportamento sicuro

- Una fascia giornaliera, tutti i giorni, con risoluzione di un minuto. Il controllo avviene circa ogni secondo, anche senza browser.
- L'istante di accensione è incluso, quello di spegnimento è escluso. `08:00 → 20:00` significa acceso dalle 08:00 fino alle 19:59:59.
- Se l'accensione è successiva allo spegnimento, la fascia passa dalla mezzanotte. Orari uguali vengono rifiutati: non significano acceso 24 ore.
- Cambiare gli orari in manuale conserva lo stato manuale corrente. Cambiarli in automatico ricalcola subito lo stato.
- Il passaggio da automatico a manuale spegne sempre l'uscita; da manuale ad automatico si applica subito la fascia.
- Il controller parte spento. Dopo il caricamento della configurazione può accendersi se è attiva la modalità automatica e l'ora rientra nella fascia. Il comando manuale ON non viene persistito.
- Si segue l'ora locale: al salto primaverile si applica il primo orario esistente; nell'ora ripetuta autunnale vale la stessa fascia per entrambe le occorrenze. La durata indicata in dashboard è nominale: i giorni del cambio dell'ora possono avere durata effettiva diversa.
- Le richieste HTTP e lo scheduler condividono un lock. Un lock di processo impedisce due istanze sulla stessa `DATA_DIR`. Non avviare istanze reali con directory differenti: entrambe tenterebbero di possedere gli stessi pin.
- Errori GPIO, di persistenza o dello scheduler bloccano ulteriori accensioni e richiedono lo spegnimento. Per riprendere serve un riavvio. Lo stato sconosciuto viene restituito come `null`, mai tradotto in una conferma di spegnimento.
- `Ctrl+C`, SIGTERM e chiusura normale spengono e rilasciano il controller. Il watchdog systemd controlla il thread dello scheduler: in caso di blocco o guasto senza heartbeat, dopo circa 20 secondi richiede l'arresto e riavvia il processo. Sono previsti limiti ai tentativi. Dopo un riavvio automatico una fascia attiva può riaccendere il relè.

L'orologio del sistema deve essere corretto. Il Pi 3 non ha un RTC con batteria integrato: dopo un blackout senza rete l'ora può essere errata. Prima di usare automazioni reali, configura NTP e verifica `timedatectl status`. Per attendere la sincronizzazione al boot, puoi abilitare `systemd-time-wait-sync.service` sul Raspberry, verificandone la disponibilità sulla tua versione di OS. Il servizio applicativo è ordinato dopo `time-sync.target`. **Questo ordine da solo non garantisce una sincronizzazione se non è presente un servizio che la attende.** Se il funzionamento senza rete e dopo blackout è necessario, aggiungi un RTC e una strategia di validazione dell'ora prima di abilitare la modalità automatica. La prima versione non implementa tale interblocco.

## Accesso da smartphone e LAN

L'accesso di rete è disabilitato per impostazione iniziale. Per abilitarlo, genera un token sul computer che ospita Flask:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Inserisci il valore soltanto nel file `.env` locale e sostituisci l'IP di esempio con quello reale del PC o del Raspberry:

```dotenv
HARDWARE_MODE=mock
NETWORK_MODE=lan
API_TOKEN=INCOLLA_QUI_IL_TOKEN_CASUALE_GENERATO
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],192.168.1.50,greenhouse.local
```

Riavvia il server, collega il telefono alla stessa rete e apri `http://192.168.1.50:5000`. La dashboard chiederà il token. Il token rimane soltanto nella memoria della scheda e va reinserito dopo un refresh completo o una nuova apertura. Non compare nei file HTML o nei parametri URL. Non inviarlo a servizi esterni. Su Windows, se necessario, consenti la porta solo nel profilo di rete privata del firewall.

Ogni API, anche quella di lettura, richiede un token Bearer ai client di rete. `/health` è pubblico e restituisce solo `ok` o `degraded`. I comandi richiedono JSON, un header personalizzato e origine coerente. Non viene abilitato CORS. L'header Host viene verificato contro la lista esplicita per limitare DNS rebinding. Gli header di proxy non sono considerati attendibili.

**Eccezione locale intenzionale:** un client che si collega da loopback **e** usa un Host loopback (`localhost` / `127.0.0.1` / `[::1]`) può controllare il sistema senza token, anche in LAN. Permette al touchscreen di avviarsi autonomamente; chi ha accesso al sistema operativo locale è considerato autorizzato. Sono comunque applicati i controlli di origine e dell'header personalizzato. Un client LAN non può ottenere questa eccezione cambiando solo l'header Host. Non collocare un reverse proxy che trasformi client remoti in richieste loopback autorizzate.

La modalità LAN usa HTTP: il token non è cifrato sul trasporto. Usala soltanto su una rete privata fidata; su reti condivise serve TLS con un'architettura di autenticazione verificata. Non aprire port forwarding sul router, non pubblicare il servizio su Internet e non creare tunnel pubblici. La prima versione usa un token condiviso, senza account o ruoli.

## Preparare e trasferire il progetto

Dal PC:

```powershell
.\.venv\Scripts\python.exe scripts/export_project.py
scp .\artifacts\smart-greenhouse.zip mario@greenhouse.local:/home/mario/
ssh mario@greenhouse.local
```

Sostituisci utente e hostname. Abilita prima SSH sul Raspberry e verifica che i due dispositivi siano nella stessa LAN. L'archivio include codice, test, documentazione e template di configurazione; non include `.venv`, dati, `.env`, impostazioni IDE o token. Non trasferire l'ambiente virtuale Windows sul Pi.

**I comandi seguenti vanno eseguiti solo sul Raspberry Pi OS Desktop**, mai nel terminale del PC:

```bash
mkdir -p ~/SmartGreenhouse
python3 -m zipfile -e ~/smart-greenhouse.zip ~/SmartGreenhouse
cd ~/SmartGreenhouse
bash deploy/install.sh
```

Per aggiornare un'installazione, arresta prima `sudo systemctl stop smart-greenhouse`, trasferisci il nuovo archivio, estrailo nella stessa cartella e riesegui l'installer. Conserva `.env` e `data/`; non estrarre sopra un server ancora attivo.

## Installazione sul Raspberry Pi 3B

Prepara Raspberry Pi OS **Desktop 32-bit**, con Python 3.10 o successivo, alimentazione adeguata e microSD affidabile. L'installer richiede rete durante l'installazione, `sudo` e l'esecuzione come utente del desktop, in un percorso senza spazi. Non occorre usare il nome utente storico `pi`.

`deploy/install.sh`:

1. Verifica Linux, modello Raspberry e OS compatibile; su un PC rifiuta di procedere.
2. Installa Python venv, GPIO Zero, backend `lgpio` e Chromium dai pacchetti dell'OS.
3. Crea `.venv-pi` con accesso ai pacchetti di sistema e installa `requirements-pi.txt`. Questo permette di usare il backend GPIO fornito dall'OS senza compilarlo sul PC.
4. Crea una nuova `.env` in modalità **mock**, se assente; conserva quella esistente. Non cambia automaticamente un'installazione già configurata in real.
5. Aggiunge l'utente al gruppo `gpio`, crea e abilita il servizio systemd con l'utente reale. Non esegue Flask come root.
6. Installa l'autostart XDG per i desktop X11 e aggiunge l'avvio a `~/.config/labwc/autostart` per Wayland/labwc, preservando le righe esistenti. Il lock del Kiosk evita doppi avvii.

Per la sandbox del servizio l'installer richiede `DATA_DIR=data`. Se vuoi una directory esterna, modifica insieme la configurazione e `ReadWritePaths` nell'unit systemd. Prima di rilanciare l'installer con hardware in `real`, scollega il carico: l'installazione può riavviare un servizio guasto.

Verifica prima la dashboard in mock. Dopo le verifiche hardware a carico scollegato, arresta il servizio, imposta pin e polarità corretti in `.env`, poi riavvia:

```bash
sudo systemctl stop smart-greenhouse
nano .env
# HARDWARE_MODE=real
# RELAY_PIN=17
# RELAY_ACTIVE_HIGH=false   # solo se è la polarità effettiva del tuo modulo
sudo systemctl start smart-greenhouse
systemctl status smart-greenhouse
journalctl -u smart-greenhouse -n 80 --no-pager
```

Nessun fallback silenzioso alla simulazione: se il dispositivo o `lgpio` falliscono, l'avvio reale fallisce. GPIO Zero viene importato soltanto nel controller reale. `RELAY_PIN` usa BCM (GPIO17 corrisponde al pin fisico 11 sul connettore a 40 pin), non il numero fisico del connettore.

## Touchscreen DSI e Chromium Kiosk

Collega il flat DSI **a Raspberry spento e disalimentato**, secondo le istruzioni del modello di display. Il display ufficiale compatibile viene normalmente rilevato dall'OS; i pannelli di terzi possono richiedere overlay/driver del produttore. Non vengono imposti overlay o rotazioni generici, perché dipendono dal pannello.

Sul Raspberry:

1. Verifica nel desktop che immagine, tocco e orientamento siano corretti prima di avviare la webapp. Per il display ufficiale da 7 pollici prova la risoluzione 800 × 480.
2. Abilita **Desktop Autologin** nelle impostazioni o in `sudo raspi-config` (System Options / Boot / Auto Login; i nomi possono variare con la release).
3. Disattiva **Screen Blanking** nelle impostazioni display. Su Wayland usa la configurazione del compositor; su X11 gli eventuali comandi `xset` sono specifici della sessione X11. L'installer non cambia automaticamente il risparmio energetico o il sistema grafico.
4. Se serve inserire testo da touchscreen, abilita la tastiera virtuale del desktop. Gli orari possono essere selezionati con i controlli nativi del browser.
5. Riavvia il Pi e verifica il percorso completo OS → servizio → desktop → Kiosk → dashboard. Attiva LAN solo dopo la prova locale.

`deploy/kiosk.py` viene eseguito come utente della sessione grafica. Mantiene una pagina di attesa su **127.0.0.1:5001**, separata da Flask; verifica il server e apre la dashboard su 127.0.0.1 alla porta configurata. Quando il server scompare riapre l'attesa, e quando Chromium termina lo rilancia. Il polling della dashboard recupera anche le interruzioni brevi. Gli errori hardware con HTTP 503 sono considerati un server raggiungibile, così la dashboard può mostrarli. La porta 5001 deve rimanere libera e non viene esposta in LAN.

Il supervisore usa un profilo Chromium dedicato in `~/.local/share/smart-greenhouse/chromium`. Non disabilita la sandbox di Chromium. Il meccanismo recupera la chiusura del browser e l'indisponibilità HTTP del backend; non garantisce il recupero da un blocco totale dell'OS o del processo grafico. Per uscire usa `Alt+F4` dopo aver disabilitato l'autostart, oppure una console/SSH. Per disabilitare il Kiosk rimuovi **solo** la riga Smart Greenhouse da `~/.config/labwc/autostart` e il file `~/.config/autostart/smart-greenhouse-kiosk.desktop`, poi termina il supervisore o esci dalla sessione. Non cancellare l'intero autostart del desktop.

## Sicurezza del relè e limiti hardware

**Non alimentare la lampada dai pin GPIO.** I pin sono segnali logici a 3,3 V; usa un modulo relè/driver compatibile e un'alimentazione adatta. Non portare tensioni di rete o segnali a 5 V sui GPIO. La scelta dell'interfaccia, dell'isolamento e delle masse dipende dal modulo: verifica lo schema del produttore.

- Per carichi di rete, fai progettare e realizzare il cablaggio a personale qualificato. Servono relè/contattore idoneo a tensione, corrente e spunto della lampada, isolamento, involucro, protezioni e distanze elettriche adeguate. La serra è un ambiente umido: non lasciare contatti di rete esposti.
- Preferisci una configurazione fisica che lasci il carico spento quando il relè non è eccitato, verificando i contatti normalmente aperti sul modulo effettivo.
- `initial_value=False` imposta lo stato logico OFF con la polarità scelta. Allo spegnimento viene richiesto OFF prima di rilasciare il pin. **Il rilascio del GPIO può riportarlo ad alta impedenza.** Verifica pull-up/pull-down esterni e comportamento del driver.
- Durante boot, reboot, perdita di alimentazione e prima che Python prenda il controllo, i GPIO possono essere ingressi, flottanti o cambiare stato. Il software non può eliminarlo. Usa polarizzazione e interblocchi hardware adeguati per impedire impulsi indesiderati.
- Il valore mostrato è il comando logico, senza feedback dai contatti, misura di corrente o conferma che la lampada sia realmente accesa/spenta. Un relè incollato non viene rilevato da questa applicazione.
- Un crash brutale, `kill -9`, blocco del kernel, relè guasto o saldato può lasciare il carico acceso. Il watchdog software può riavviare un processo, ma non garantisce una disconnessione elettrica. Per carichi critici servono interruttore fisico, interblocco/termostato indipendente o watchdog hardware che disecciti il contattore.

Questi sono limiti del controllo software: l'inizializzazione sicura non sostituisce un circuito progettato per il guasto.

## Test e verifiche

Sul PC:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

I test coprono API e input invalidi, inizializzazione mock senza import GPIO, salvataggio e riavvio, fasce ordinarie/notturne e confini, cambio dell'ora, scheduler senza browser, serializzazione dei comandi, lock di processo, protezioni LAN/origine/Host, assenza sensori reali, guasti GPIO e SQLite, stato sconosciuto e chiusura sicura. L'adattatore reale viene provato con un dispositivo fittizio in entrambe le polarità: **non sono test elettrici sul Raspberry**.

Per ripetere anche lo smoke test del browser, con Chrome/Chromium/Edge già installato:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe scripts/check_ui.py
```

Il test usa un server mock con dati temporanei e una porta libera; non modifica la configurazione dell'utente. Verifica comandi reali dall'interfaccia, salvataggio degli orari, blocco dei comandi in automatico, conservazione delle modifiche durante il polling, errore sugli orari uguali e riconnessione dopo un'interruzione del server. Produce screenshot a 1440, 800 e 390 pixel in `artifacts/ui/`. Non scarica browser né richiede Node. Se il browser non è trovato, imposta `CHROME_PATH` al suo eseguibile. Le dipendenze UI sono facoltative e non vengono installate sul Raspberry dall'installer.

La verifica su Raspberry rimane necessaria:

1. Con carico scollegato, verifica pin BCM, livelli elettrici, polarità, permessi `gpio` e assenza di impulsi all'avvio/arresto.
2. Prova ON/OFF e automatico, fascia notturna, salvataggio e riavvio del servizio. Verifica fisicamente il relè; confrontare solo l'API non basta.
3. Verifica spegnimento a SIGTERM, ripristino dopo crash, watchdog, perdita di rete, database non scrivibile e comportamento in blackout. Usa inizialmente un carico di prova sicuro.
4. Verifica ora/NTP all'avvio, assenza rete e variazioni dell'ora. Verifica i limiti del sistema durante il boot prima di usare automazioni reali.
5. Prova avvio ritardato del server, restart del servizio, chiusura di Chromium, login automatico, tocco, tastiera e sospensione schermo.
6. Con un telefono prova rifiuto senza token, accesso con token, aggiornamento tra più browser e firewall della LAN.
7. Controlla uso RAM, temperatura e stabilità per almeno un ciclo giornaliero sul Pi 3 da 1 GB; mantieni una sola scheda Chromium e disattiva applicazioni desktop superflue.

Il software e gli script Raspberry sono stati preparati sul PC; non sono state apportate configurazioni di sistema al Raspberry né eseguite prove su hardware fisico.

## API

Le risposte sono JSON. Le mutazioni richiedono `Content-Type: application/json` e `X-Greenhouse-Request: 1`; in LAN aggiungi `Authorization: Bearer <token>` per i client remoti. Se invii `Origin`, deve coincidere con schema, host e porta della richiesta.

| Metodo | Endpoint | Corpo / risultato |
| --- | --- | --- |
| GET | `/health` | Stato minimo; HTTP 200 o 503 |
| GET | `/api/status` | Lampada, orari, sensori e sistema |
| POST | `/api/lamp` | `{"on": true}` o `{"on": false}`, solo in manuale |
| PUT | `/api/settings` | Uno o più tra `mode`, `on_time`, `off_time` |

Esempio sul PC, PowerShell:

```powershell
Invoke-RestMethod http://localhost:5000/api/status
Invoke-RestMethod http://localhost:5000/api/lamp -Method Post -ContentType 'application/json' -Headers @{'X-Greenhouse-Request'='1'} -Body '{"on":true}'
Invoke-RestMethod http://localhost:5000/api/settings -Method Put -ContentType 'application/json' -Headers @{'X-Greenhouse-Request'='1'} -Body '{"mode":"auto","on_time":"22:00","off_time":"06:00"}'
```

Codici d'errore: 400 per input o Host invalidi; 401 per token assente/errato; 403 per origine/header/accesso locale non consentiti; 409 per comando manuale in automatico; 413 per corpo troppo grande; 503 per guasto del servizio. I campi sconosciuti sono rifiutati. Un errore non viene trasformato in successo.

## Organizzazione ed estensioni

```text
app.py                      Factory Flask, API, sicurezza e avvio Waitress
config.py                   Configurazione validata da ambiente/.env
scheduler.py                Thread unico e regole orarie, heartbeat systemd
hardware/                   Interfaccia, MockGPIOController, RealGPIOController
services/lamp.py            Stato e lock, modalità, gestione guasti
services/storage.py         Configurazione SQLite
services/sensors.py         Punto di estensione per sensori
services/instance_lock.py   Lock Windows/Linux del processo
templates/index.html        Dashboard
static/                     CSS, JavaScript e icona SVG locali
deploy/                     Installer Raspberry, unit, Kiosk e autostart
scripts/export_project.py   Archivio trasferibile senza segreti
tests/                      Test senza hardware
```

Per aggiungere sensori implementa un provider nel servizio di monitoraggio, mantenendo `value: null` / `status: unavailable` in caso di assenza o errore. I sensori reali futuri devono avere timeout, identificazione e data della lettura: non bloccare il thread che gestisce il relè. Per altri attuatori aggiungi controller/servizi separati con le proprie regole; non usare direttamente i GPIO negli endpoint Flask.

## Fonti tecniche

La configurazione segue la [documentazione Flask per Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/), la [API OutputDevice di GPIO Zero](https://gpiozero.readthedocs.io/en/stable/api_output.html), il [manuale systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html), il [tutorial Kiosk ufficiale Raspberry Pi](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/) e la [documentazione del Touch Display](https://www.raspberrypi.com/documentation/accessories/display.html). Le impostazioni del desktop dipendono dalla release installata; per labwc e X11 sono previsti punti di avvio distinti.
