# Smart Greenhouse

Webapp leggera per sviluppare sul PC e controllare una serra con Raspberry Pi 3 Model B. Python 3.10+, Flask, HTML/CSS/JavaScript vanilla, SQLite. Nessun Node.js, Docker, servizio cloud o asset esterno. Interfaccia in italiano, utilizzabile anche su touchscreen da 800 × 480 con scorrimento verticale.

Per l'utilizzo attuale del progetto, il Raspberry può funzionare **senza schermo e senza desktop all'avvio**, con accesso dal browser di PC o telefono sulla stessa LAN. Il servizio Flask e lo scheduler sono indipendenti dal desktop; il Kiosk rimane un'opzione per chi utilizza un touchscreen locale.

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

Le letture **24,6 °C** e **62%** in mock sono esempi fissi e mostrano esplicitamente **Simulato**. Non sono una simulazione termica. In modalità `real` sono supportati **DS18B20 per la temperatura** e **DHT11 per l'umidità relativa dell'aria**. Se disabilitati, assenti, guasti o senza letture recenti, l'API restituisce `null` e la dashboard mostra **Non disponibile**, con lo stato e il motivo.

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
| `DS18B20_ENABLED` | `false` | Abilita la temperatura reale, solo in `HARDWARE_MODE=real` |
| `DS18B20_PIN` | `4` | BCM del bus 1-Wire: deve corrispondere all'overlay del kernel |
| `DS18B20_ID` | vuoto | ID della sonda, ad esempio `28-000000abcdef`; automatico solo se è presente una sola sonda |
| `DHT11_ENABLED` | `false` | Abilita l'umidità reale, solo in `HARDWARE_MODE=real` |
| `DHT11_PIN` | `22` | BCM del segnale DHT11: deve corrispondere all'overlay del kernel |
| `DHT11_DEVICE` | vuoto | Nome IIO, ad esempio `iio:device0`; automatico solo con un DHT rilevato |

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

Per la sandbox del servizio l'installer richiede `DATA_DIR=data`. Il processo viene avviato con directory corrente `data/`, perché `lgpio` crea le proprie pipe di notifica `.lgd-nfy*` nella directory corrente già durante l'importazione. Codice e configurazione rimangono in sola lettura. L'applicazione risolve i percorsi dal progetto, quindi il database rimane `data/greenhouse.sqlite3`, senza una seconda directory `data/data`. Se vuoi una directory esterna, modifica insieme la configurazione, `WorkingDirectory` e `ReadWritePaths` nell'unit systemd. Prima di rilanciare l'installer con hardware in `real`, scollega il carico: l'installazione può riavviare un servizio guasto.

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

### Errore `.lgd-nfy` all'avvio in modalità reale

Se il journal riporta `xCreatePipe: Can't set permissions` nella cartella del progetto e poi `FileNotFoundError: .lgd-nfy-3`, controlla la directory corrente del servizio. Una versione precedente del template avviava Python nella cartella del codice, che la sandbox systemd rende di sola lettura. L'errore si presenta durante l'importazione di `lgpio`, prima di richiedere il pin: quel traceback non dimostra un guasto del relè o un pin errato.

Il template aggiornato avvia il processo in `data/`, già autorizzata in scrittura. Per correggere un'installazione esistente senza reinstallare, esegui **nella sessione SSH sul Raspberry**, adattando il percorso della prima riga:

```bash
cd ~/ProgettoSerra
sudo systemctl stop smart-greenhouse
mkdir -p data
sudo mkdir -p /etc/systemd/system/smart-greenhouse.service.d
printf '[Service]\nWorkingDirectory=%s/data\n' "$PWD" | sudo tee /etc/systemd/system/smart-greenhouse.service.d/working-directory.conf
sudo systemctl daemon-reload
sudo systemctl reset-failed smart-greenhouse
sudo systemctl start smart-greenhouse
systemctl status smart-greenhouse --no-pager -l
curl -sS --max-time 5 http://127.0.0.1:5000/health
```

Se hai cambiato `PORT`, adatta anche l'URL dell'ultima riga. Il file di override persiste dopo i riavvii. `reset-failed` rimuove il blocco dovuto ai precedenti avvii falliti. La correzione conserva `.env`, orari, database e protezioni della sandbox. Il servizio deve risultare `active (running)` e `/health` rispondere `{"status":"ok"}`; il comando GPIO e il carico devono comunque essere verificati sull'hardware reale. Se compare un errore diverso, leggi il nuovo journal prima di cambiare altre impostazioni.

Riferimenti: [directory di lavoro systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#WorkingDirectory=) e [directory di lavoro della libreria lgpio](https://github.com/joan2937/lg/blob/master/lgUtil.c).

## Sensori DS18B20 e DHT11

L'applicazione legge una sonda **DS18B20** per la temperatura e un **DHT11** per l'umidità relativa dell'aria. Il DHT11 contiene anche un termometro, ma non viene usato come sostituto del DS18B20: se la sonda manca, la temperatura rimane non disponibile. Le confezioni da due/tre unità non richiedono di collegarle tutte.

I sensori usano i driver Linux già previsti da Raspberry Pi OS: `w1_therm` tramite l'overlay `w1-gpio` e IIO tramite l'overlay `dht11`. Non sono necessarie nuove dipendenze Python, compilatori o librerie DHT sul PC. L'installer dell'app non modifica automaticamente gli overlay di boot.

### Collegamenti previsti sul Raspberry Pi 3B

Collega i sensori a Raspberry spento e disalimentato. Per il relè già configurato su BCM15, questa disposizione mantiene i tre segnali separati:

| Dispositivo / segnale | GPIO BCM | Pin fisico del connettore a 40 pin |
| --- | --- | --- |
| Relè lampada già configurato | 15 | 10 |
| DS18B20: DQ / DATA | 4 | 7 |
| DHT11: DATA / OUT / S | 22 | 15 |
| Alimentazione sensori VDD / VCC | — | 1 oppure 17: **3,3 V** |
| Massa sensori GND | — | 6 oppure 9: **GND** |

**GPIO15 e pin fisico 15 sono distinti:** il secondo è GPIO22, usato qui per il DHT11. La numerazione BCM vale sia nel `.env` sia negli overlay. Verifica che gli altri dispositivi non usino questi pin.

Per il **DS18B20 a tre fili**, collega VDD a 3,3 V, GND alla massa e DATA a BCM4. Serve una resistenza **4,7 kΩ fra DATA e 3,3 V**, salvo che sia già presente su un adattatore. Usa l'alimentazione a tre fili, senza modalità parassita. Identifica i fili con lo schema della sonda AZDelivery: non affidarti soltanto ai colori, che possono variare. La protezione della sonda non rende impermeabili giunzioni, resistenza o Raspberry.

Per il **DHT11**, usa VCC a 3,3 V, GND alla massa e DATA a BCM22. Per la variante a **tre pin**, segui le etichette sul modulo: l'ordine dei pin può cambiare e il pull-up può essere già presente. Per la variante a **quattro piedini**, segui il pinout del produttore, lascia NC scollegato e aggiungi un pull-up **10 kΩ fra DATA e 3,3 V** se assente. Questo collegamento mantiene il segnale nei limiti a 3,3 V del Raspberry: non collegare direttamente un'uscita con pull-up a 5 V. Il DHT11 misura l'umidità dell'aria, non del terreno; sistemalo al riparo da acqua, condensa e irrigazione diretta. Per limiti di misura e accuratezza consulta la scheda del modello ricevuto.

Riferimenti: [pinout Raspberry Pi](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html), [datasheet DS18B20](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf), [DHT11 AZDelivery e relativi schemi](https://www.az-delivery.de/en/products/5-x-dht11-temperatursensor), [pull-up DHT](https://learn.adafruit.com/dht/dht-circuitpython-code).

### Abilitare i driver sul Raspberry

Questi comandi vanno eseguiti solo sul Raspberry, anche da SSH. Con il servizio arrestato, fai una copia del file di boot e aprilo:

```bash
sudo systemctl stop smart-greenhouse
sudo cp -n /boot/firmware/config.txt /boot/firmware/config.txt.before-greenhouse-sensors
sudo nano /boot/firmware/config.txt
```

Su Bookworm/Trixie il file è `/boot/firmware/config.txt`. Se la tua installazione usa un percorso diverso, verifica quello effettivo prima di modificarlo. In fondo al file, sotto una sezione `[all]`, aggiungi **una sola volta**, adattando eventuali righe già presenti:

```ini
[all]
dtoverlay=w1-gpio,gpiopin=4
dtoverlay=dht11,gpiopin=22
```

Non duplicare un overlay 1-Wire già attivato da `raspi-config`. Non configurare entrambi i sensori su BCM4: è il valore predefinito di entrambi gli overlay. I pin devono coincidere con quelli del cablaggio e del `.env`. Il driver kernel prende possesso dei pin dei sensori; l'app controlla direttamente con GPIO Zero soltanto quello del relè.

Fonti: [overlay ufficiali Raspberry Pi](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/arch/arm/boot/dts/overlays/README), [driver DS18B20](https://docs.kernel.org/w1/slaves/w1_therm.html), [driver DHT11](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/drivers/iio/humidity/dht11.c).

### Configurare l'app e verificare le misure

Prima trasferisci sul Raspberry il codice aggiornato, a servizio fermo, conservando `.env` e `data/`. Puoi usare `scripts/export_project.py` e la procedura SSH/SCP descritta sopra. Non è necessario reinstallare le dipendenze per questi due sensori: il supporto è nel kernel e nella libreria standard Python.

Nel `.env` **aggiungi o aggiorna** queste impostazioni, conservando rete, token, polarità del relè e le altre impostazioni esistenti:

```dotenv
HARDWARE_MODE=real
DS18B20_ENABLED=true
DS18B20_PIN=4
DS18B20_ID=
DHT11_ENABLED=true
DHT11_PIN=22
DHT11_DEVICE=
```

Le variabili `*_PIN` nel `.env` non attivano gli overlay: documentano la configurazione e consentono di rifiutare conflitti tra sensori e relè. Il kernel deve essere configurato separatamente come sopra. I sensori restano disabilitati per default nelle nuove installazioni, finché non imposti esplicitamente `true`. In mock rimangono sempre simulati, anche se queste opzioni sono abilitate.

Se colleghi il **DS18B20 a GPIO17 (pin fisico 11)**, sostituisci la riga dell'overlay 1-Wire con `dtoverlay=w1-gpio,gpiopin=17` e imposta `DS18B20_ENABLED=true` e `DS18B20_PIN=17` nel `.env`. Non lasciare attiva anche la vecchia riga 1-Wire su BCM4. Collega il pull-up da 4,7 kΩ fra il DATA effettivamente usato (ora BCM17) e 3,3 V. Il relè e il DHT11 devono restare su pin diversi: ad esempio relè BCM15 e DHT11 BCM22, se questi sono i collegamenti reali. In particolare, il valore di esempio `RELAY_PIN=17` non può essere usato insieme alla sonda su BCM17. Arresta il servizio prima della modifica e riavvia il Raspberry dopo aver salvato l'overlay: il solo riavvio di Flask non modifica il pin del bus kernel.

Dopo aver salvato gli overlay e il `.env`, riavvia il Raspberry con `sudo reboot`; la sessione SSH si chiuderà. Quindi riconnettiti e controlla:

```bash
ls /sys/bus/w1/devices/28-*/w1_slave
cat /sys/bus/iio/devices/iio:device*/name
systemctl status smart-greenhouse --no-pager -l
curl -sS http://127.0.0.1:5000/api/status
```

L'ultima richiesta è eseguita sul Raspberry tramite loopback, quindi non richiede il token LAN. La dashboard locale mostra la fonte DS18B20/DHT11 e l'ora della misura; i dati disponibili hanno `status: "ok"`. Il kernel converte la temperatura in millesimi di grado e l'umidità in millesimi di percentuale: l'app espone rispettivamente °C e %.

Se sono collegate **due sonde DS18B20**, scegli quella da visualizzare impostando `DS18B20_ID` con l'ID reale mostrato da `ls`, senza `/w1_slave`. Non impostare l'ID di esempio della documentazione. In assenza della sonda selezionata, l'app non passa silenziosamente all'altra. Per più dispositivi DHT sullo stesso Raspberry imposta `DHT11_DEVICE` con il nome IIO corretto, verificando nuovamente la scelta dopo modifiche hardware: l'indice IIO può cambiare fra avvii.

### Errori, frequenza e verifiche fisiche

Ogni sensore ha un worker indipendente: una lettura ogni circa **5 secondi**, con l'eventuale tempo di conversione del driver. Le richieste HTTP leggono soltanto la cache e non aspettano l'hardware. Il DS18B20 deve superare il CRC; il kernel verifica checksum e tempi del DHT11. Valori fuori dai limiti fisici vengono rifiutati.

Un errore invalida subito il valore mostrato. Un dato senza aggiornamenti per **20 secondi** diventa `stale` e viene nascosto; lo stesso limite segnala una prima lettura bloccata. Non viene inventato né mantenuto visibile come attuale un valore vecchio. La cache si ripristina automaticamente quando ricominciano le letture. L'ora dell'ultima lettura riuscita rimane nei metadati, insieme all'età del dato e al motivo dell'errore.

Il guasto di un sensore non spegne né blocca automaticamente la lampada, la cui logica rimane manuale/oraria. `/health` continua a indicare la salute del servizio lampada; `/api/status` espone separatamente `system.sensors_healthy`. Per eventuali automazioni basate su temperatura o umidità serviranno regole e interblocchi dedicati.

Se non ci sono misure, consulta `journalctl -u smart-greenhouse -n 60 --no-pager` e, per errori del driver, `sudo journalctl -k -b -n 80 --no-pager`. Verifica overlay, alimentazione, pull-up, contatti, pin, ID e assenza di condensa. Il messaggio DHT11 può indicare un timeout o un errore I/O dovuto alla decodifica del segnale: non sostituirlo con letture simulate.

Prima dell'uso in serra, confronta le misure con uno strumento di riferimento, controlla che la sonda scelta sia quella fisicamente prevista e verifica almeno scollegamento, riconnessione, riavvio e funzionamento sotto il carico reale di Chromium. I test sul PC simulano i file sysfs e gli errori dei driver; non attestano cablaggio, precisione o affidabilità elettrica dei sensori acquistati.

## Uso senza schermo: browser da PC e telefono

Esegui la configurazione nella sessione SSH sul Raspberry. Il servizio `smart-greenhouse` è associato a `multi-user.target`: continua ad avviarsi e a gestire lampada e sensori anche senza sessione grafica e senza browser aperti.

Per disattivare il desktop nei prossimi avvii e confermare l'avvio del servizio:

```bash
sudo systemctl set-default multi-user.target
sudo systemctl enable smart-greenhouse
systemctl get-default
```

L'ultimo comando deve restituire `multi-user.target`. Il cambiamento del target di default si applica al prossimo avvio; non arresta subito il desktop già aperto. Puoi mantenere installati i pacchetti grafici: quando il desktop non parte, i suoi autostart non lanciano Chromium o il Kiosk. L'installer attuale prepara anche i file Kiosk, ma il servizio Flask non ne dipende.

### Abilitare prima l'accesso dalla rete locale

Se nel `.env` è rimasto `NETWORK_MODE=local`, il server accetta solo connessioni sul Raspberry. Prima di spegnere o scollegare lo schermo, prepara la modalità LAN e verifica l'accesso dal PC/telefono.

```bash
cd ~/ProgettoSerra
.venv-pi/bin/python -c "import secrets; print(secrets.token_urlsafe(32))"
nano .env
```

Il comando Python stampa un token casuale. Copialo nel `.env`, modificando le righe già presenti (senza duplicarle) e mantenendo i parametri di relè e sensori. Esempio per il Raspberry `raspberry-serra`, con IP Wi-Fi `192.168.1.9` rilevato durante la configurazione:

```dotenv
NETWORK_MODE=lan
API_TOKEN=INCOLLA_QUI_IL_TOKEN_CASUALE_GENERATO
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],raspberry-serra.local,192.168.1.9
```

Sostituisci l'IP se è cambiato; per usare anche l'indirizzo Ethernet aggiungi quello attuale alla lista. Conserva il token sul tuo dispositivo e non inviarlo in chat. Il browser di rete lo richiede per accedere alle API. Vedi anche la sezione Accesso da smartphone e LAN per i limiti dell'accesso HTTP su una rete privata.

Applica le impostazioni:

```bash
sudo systemctl restart smart-greenhouse
systemctl status smart-greenhouse --no-pager -l
```

Con servizio `active (running)`, apri dal PC o telefono **http://192.168.1.9:5000** oppure **http://raspberry-serra.local:5000** se il dispositivo risolve il nome mDNS. Entrambi i dispositivi devono essere nella stessa rete e il nome/IP usato deve essere presente in `ALLOWED_HOSTS`. Verifica la dashboard prima di riavviare il Raspberry.

Per scollegare il flat DSI, arresta il Raspberry con `sudo poweroff`, attendi lo spegnimento e togli l'alimentazione prima di scollegare il display. Riaccendendo, il sistema parte senza desktop e il servizio rimane disponibile in LAN. Puoi verificare da SSH con `systemctl get-default`, `systemctl is-active smart-greenhouse` e `nmcli device status`.

Per tornare in futuro all'avvio grafico, imposta `sudo systemctl set-default graphical.target` e riavvia. La rimozione del desktop o di Chromium non è necessaria per il funzionamento senza schermo.

Riferimenti: [target di avvio systemd](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html#set-default%20TARGET) e [avvio console/desktop su Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/configuration.html).

## Touchscreen DSI e Chromium Kiosk (opzionale)

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

I test coprono API e input invalidi, inizializzazione mock senza import GPIO, salvataggio e riavvio, fasce ordinarie/notturne e confini, cambio dell'ora, scheduler senza browser, serializzazione dei comandi, lock di processo, protezioni LAN/origine/Host, guasti GPIO e SQLite, stato sconosciuto e chiusura sicura. Per DS18B20/DHT11 sono verificati conversione delle unità, CRC/formati errati, sensori assenti o multipli, selezione dell'ID, conflitti di pin, scadenza e ripristino dei dati, isolamento di un sensore bloccato rispetto all'altro e alle API lampada, assenza di fallback a misure inventate. L'adattatore GPIO reale viene provato con un dispositivo fittizio in entrambe le polarità: **non sono test elettrici sul Raspberry**.

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
hardware/sensors.py         Lettori kernel DS18B20 e DHT11
services/sensors.py         Worker separati, cache e scadenza delle letture
services/instance_lock.py   Lock Windows/Linux del processo
templates/index.html        Dashboard
static/                     CSS, JavaScript e icona SVG locali
deploy/                     Installer Raspberry, unit, Kiosk e autostart
scripts/export_project.py   Archivio trasferibile senza segreti
tests/                      Test senza hardware
```

Per aggiungere sensori implementa un reader in `hardware/sensors.py` e associalo a un worker nel servizio di monitoraggio. Mantieni `value: null` in caso di assenza, errore o dato scaduto, con identificazione, timestamp e motivo. Il reader non deve bloccare il thread che gestisce il relè. Per altri attuatori aggiungi controller/servizi separati con le proprie regole; non usare direttamente i GPIO negli endpoint Flask.

## Fonti tecniche

La configurazione segue la [documentazione Flask per Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/), la [API OutputDevice di GPIO Zero](https://gpiozero.readthedocs.io/en/stable/api_output.html), il [manuale systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html), il [tutorial Kiosk ufficiale Raspberry Pi](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/) e la [documentazione del Touch Display](https://www.raspberrypi.com/documentation/accessories/display.html). Le impostazioni del desktop dipendono dalla release installata; per labwc e X11 sono previsti punti di avvio distinti.
