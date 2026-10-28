# RSEQ Team Calendar — module complémentaire Home Assistant / Home Assistant add-on

![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-add--on-41BDF5.svg)
![Licence](https://img.shields.io/badge/licence-Apache%202.0-green.svg)

[Français](#français) | [English](#english)

---

## Français

### Description

**RSEQ Team Calendar** lit le calendrier et le classement d'une ou de plusieurs équipes sur les sites du
**RSEQ** (Réseau du sport étudiant du Québec) et les publie dans Home Assistant sous forme de **capteurs
MQTT** (découverte automatique *MQTT Discovery*).

Deux types de pages sont pris en charge :

| Site | Type d'URL | Lecture |
|---|---|---|
| **RSEQ-QCA** (nouveau site, saison 2026-2027) | page de **ligue** `https://rseqqca.com/ligue/<identifiant>` | HTML direct (aucun navigateur) ; les matchs de l'équipe sont filtrés selon `team_name` |
| **diffusion.rseq.ca** (ancien site) | page d'**équipe** `https://diffusion.rseq.ca/Default?Type=Team&TeamId=<identifiant>` | Chromium sans interface (Selenium), démarré seulement si une équipe utilise ce site |

En option, le module peut aussi ajouter le **prochain match** de chaque équipe dans un calendrier Home
Assistant (voir [Événements de calendrier](#événements-de-calendrier-facultatif)).

> Le dossier du module dans ce dépôt s'appelle `example/` (nom hérité du gabarit). Il ne faut pas le
> renommer : cela casserait les installations existantes.

### Fonctionnalités

- Plusieurs équipes dans un seul module (liste `teams`), ou une seule équipe (mode historique `team_url`).
- 4 capteurs par équipe : **statut**, **prochain match**, **classement**, **dernier match**.
- Calendrier complet de l'équipe (matchs joués et à venir) dans un attribut, pour des cartes Lovelace.
- Classement de la ligue (position, MJ, V, D, N, PP, PC, MOY, PES, PTS).
- Création facultative d'un événement de calendrier HA pour le prochain match (sans doublon).
- **Rythme de mise à jour adaptatif** les jours de match (toutes les 10 min pendant un match).

### Installation

1. **Prérequis** : un courtier MQTT (par exemple le module **Mosquitto broker**) et l'intégration
   **MQTT** configurée dans Home Assistant.
2. Ajouter le dépôt : **Paramètres → Modules complémentaires → Boutique → ⋮ (en haut à droite) → Dépôts**,
   coller `https://github.com/Frazou1/rseq_calendar`, puis **Ajouter**.
   Ou cliquer sur ce bouton :

   [![Ajouter le dépôt dans Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FFrazou1%2Frseq_calendar)
3. Rafraîchir la boutique, ouvrir **RSEQ Team Calendar** et cliquer sur **Installer**.
4. Remplir l'onglet **Configuration** (voir plus bas), puis **Démarrer**.
5. Ouvrir l'onglet **Journal** : on doit voir les équipes configurées, le nombre de matchs lus et
   « Prochaine mise à jour dans N min ».

### Configuration

| Option | Type | Défaut | Rôle |
|---|---|---|---|
| `teams` | liste | `[]` | Équipes à suivre. Chaque élément : `name` (obligatoire, nom affiché et base des identifiants), `team_url` (obligatoire), `team_name` (obligatoire pour une page de ligue `rseqqca.com` : nom exact de l'équipe tel qu'il apparaît sur la page ; accents et majuscules ignorés). |
| `team_url` | texte | `""` | Mode historique, une seule équipe. Utilisé seulement si `teams` est vide ; l'équipe s'appelle alors `default`. Ne permet pas de `team_name`, donc **ne fonctionne qu'avec l'ancien site** diffusion.rseq.ca. |
| `entity_prefix` | texte | `rseq` | Préfixe des identifiants uniques des capteurs. |
| `update_interval` | entier (30 à 86400) | `3600` | Intervalle normal entre deux lectures, en secondes. |
| `mqtt_host` | texte | `core-mosquitto` | Hôte du courtier MQTT. |
| `mqtt_port` | entier | `1883` | Port du courtier MQTT. |
| `mqtt_username` | texte | `monuser` | Utilisateur MQTT. Valeur fictive : la remplacer. Si le champ n'est pas vide, il est envoyé au courtier. |
| `mqtt_password` | texte | `monpassword` | Mot de passe MQTT. Valeur fictive : la remplacer. |
| `discovery_prefix` | texte | `homeassistant` | Préfixe de découverte MQTT de Home Assistant. |
| `ha_url` | texte | `http://homeassistant.local:8123` | URL de Home Assistant, pour la création d'événements (facultatif). |
| `ha_token` | texte | `""` | Jeton d'accès longue durée (profil HA → Sécurité). Vide = aucune création d'événement. |
| `ha_calendar_entity` | texte | `calendar.rseq_equipes` | Calendrier qui reçoit les événements. |

Exemple :

```yaml
entity_prefix: rseq
teams:
  - name: Mon équipe
    team_url: https://rseqqca.com/ligue/<identifiant>
    team_name: Nom de l'équipe sur la page
  - name: Autre équipe
    team_url: https://diffusion.rseq.ca/Default?Type=Team&TeamId=<identifiant>
team_url: ""
update_interval: 3600
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_username: mon_utilisateur_mqtt
mqtt_password: mon_mot_de_passe_mqtt
discovery_prefix: homeassistant
ha_url: http://homeassistant.local:8123
ha_token: ""
ha_calendar_entity: calendar.rseq_equipes
```

Pour trouver `team_name` sur une page de ligue rseqqca.com, ouvrir la page et copier le nom de l'équipe
tel qu'il est écrit dans la liste des matchs.

### Entités créées

Pour chaque équipe, le module crée un appareil MQTT **« RSEQ – &lt;name&gt; »** et 4 capteurs.
`<slug>` est `name` en minuscules, sans accents, les autres caractères remplacés par `_`
(ex. `Mon équipe` → `mon_equipe`).

| Capteur (nom affiché) | Identifiant unique | État | Attributs principaux |
|---|---|---|---|
| RSEQ – Statut (&lt;name&gt;) | `<prefixe>_<slug>_status` | `success`, `error: calendrier vide` ou `error: <message>` | `team_url`, `last_updated` |
| RSEQ – Prochain match (&lt;name&gt;) | `<prefixe>_<slug>_next_game` | `AAAA-MM-JJ HH:MM – Visiteur @ Receveur` ou `Aucun match à venir` | `team`, `team_url`, `next_game`, `upcoming` (5 prochains), `matchs` (calendrier complet trié), `updated` |
| RSEQ – Classement (&lt;name&gt;) | `<prefixe>_<slug>_standings` | `N équipes` | `league` (`RSEQ`), `standings` (liste : `pos`, `team`, `MJ`, `V`, `D`, `N`, `PP`, `PC`, `MOY`, `PES`, `PTS`), `updated` |
| RSEQ – Dernier match (&lt;name&gt;) | `<prefixe>_<slug>_last_game` | `AAAA-MM-JJ HH:MM – Visiteur @ Receveur (score)` ou `Aucun match joué` | `team`, `team_url`, `last_game`, `updated` |

Chaque match (`next_game`, éléments de `upcoming`, `matchs`, `last_game`) contient : `no`, `jour`,
`date`, `time`, `datetime` (ISO, heure locale), `visitor`, `home`, `result`, `venue` et, pour une page
de ligue, `phase` (titre de la section, ex. saison régulière).

L'`entity_id` est généré par Home Assistant à partir du nom de l'appareil et du nom du capteur. Pour le
retrouver : **Paramètres → Appareils et services → MQTT → Appareils → « RSEQ – &lt;name&gt; »**.
Les exemples ci-dessous utilisent `sensor.rseq_mon_equipe_rseq_prochain_match_mon_equipe` : remplacez-le par le vôtre.

Sujets MQTT : `<discovery_prefix>/sensor/<identifiant unique>/config`, `/state` et `/attributes`
(messages conservés, *retain*).

#### Événements de calendrier (facultatif)

Si `ha_url`, `ha_token` et `ha_calendar_entity` sont remplis, le module appelle le **script HA
`script.create_calendar_event`** (service `script/turn_on`) pour le prochain match de chaque équipe.
**Ce script n'est pas fourni : il faut le créer.** Il reçoit les variables `calendar_entity`,
`start_date`, `end_date` (début + 2 h), `summary` (`Visiteur @ Receveur (RSEQ)`) et `description`
(`Endroit: … | Résultat: …`). Exemple, avec un calendrier modifiable (ex. intégration **Calendrier local**) :

```yaml
script:
  create_calendar_event:
    alias: Créer un événement de calendrier
    mode: queued
    fields:
      calendar_entity: {}
      start_date: {}
      end_date: {}
      summary: {}
      description: {}
    sequence:
      - action: calendar.create_event
        target:
          entity_id: "{{ calendar_entity }}"
        data:
          summary: "{{ summary }}"
          description: "{{ description }}"
          start_date_time: "{{ start_date }}"
          end_date_time: "{{ end_date }}"
```

Un seul événement est créé par prochain match : le dernier créé est mémorisé par équipe dans
`/data/last_events.json`.

### Exemples d'utilisation

Carte Markdown qui affiche les prochains matchs :

```yaml
type: markdown
title: Prochains matchs
content: >
  {% for m in state_attr('sensor.rseq_mon_equipe_rseq_prochain_match_mon_equipe', 'upcoming') or [] %}
  - **{{ m.date }} {{ m.time }}** — {{ m.visitor }} @ {{ m.home }} ({{ m.venue }})
  {% else %}
  Aucun match à venir.
  {% endfor %}
```

Automatisation : notification quand un nouveau résultat est publié :

```yaml
alias: RSEQ - Nouveau résultat
triggers:
  - trigger: state
    entity_id: sensor.rseq_mon_equipe_rseq_dernier_match_mon_equipe
conditions:
  - condition: template
    value_template: "{{ trigger.from_state is not none and trigger.to_state.state != 'Aucun match joué' }}"
actions:
  - action: notify.notify
    data:
      message: "Résultat : {{ trigger.to_state.state }}"
```

### Rythme de mise à jour

Après chaque lecture, le module calcule le délai avant la suivante (`rythme.py`) à partir de tous les
matchs lus :

- **avant un match** : réveil à l'heure du début (si elle arrive avant l'intervalle normal) ;
- **pendant un match** : toutes les **10 minutes**, jusqu'à ce qu'un résultat soit publié (4 h au plus) ;
- **après le match** : toutes les **heures** pendant **3 heures** ;
- **sinon** : l'intervalle normal (`update_interval`).

Le délai minimal est de 60 secondes. Le journal l'indique : « Prochaine mise à jour dans N min (raison) ».

Fichiers persistants dans `/data` : `options.json` (configuration), `last_events.json` (événements déjà
créés), `prochain_delai` (délai calculé), `rythme_fins.json` (fin détectée de chaque match, gardée 2 jours).

### Dépannage

Toujours commencer par l'onglet **Journal** du module.

| Message dans le journal | Cause probable | Solution |
|---|---|---|
| `[ERREUR] Aucune équipe configurée` (le module s'arrête) | `teams` vide et `team_url` vide | Ajouter au moins une équipe. |
| `[ERREUR] MQTT: …` | Courtier injoignable ou mauvais identifiants | Vérifier `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`. |
| Statut `error: team_name requis pour une page de ligue rseqqca.com` | Page de ligue sans `team_name` (ou mode `team_url` historique) | Utiliser `teams` et remplir `team_name`. |
| Statut `error: calendrier vide` et `Aucun match pour « … » — snapshot /share/rseq_last.html écrit` | `team_name` ne correspond à aucune équipe de la page, ou la page a changé | Comparer `team_name` avec le nom sur la page ; la page reçue est copiée dans `/share/rseq_last.html`. |
| `Table #CalendarTable non trouvée` / délai Selenium | Ancien site lent, modifié ou indisponible | Réessayer plus tard ; préférer une page rseqqca.com. |
| `Erreur création événement HA … HA event error 401/404` | Jeton invalide, ou script `script.create_calendar_event` absent | Créer un nouveau jeton longue durée ; créer le script (voir plus haut). |
| `Rythme adaptatif indisponible` | Erreur de calcul du délai | Le module attend alors `update_interval`. |
| Capteur toujours présent après le retrait d'une équipe | Les messages MQTT sont conservés (*retain*) | Supprimer l'appareil dans MQTT, ou effacer les sujets conservés. |

### Limites connues

- Fuseau horaire fixé à `America/Toronto` dans l'image ; l'attribut `datetime` est en heure locale,
  sans décalage horaire.
- Sur une page de ligue rseqqca.com, seul le **premier** tableau de classement de la page est lu.
- L'événement de calendrier ne couvre que le prochain match, avec une durée fixe de 2 heures.
- L'état d'un capteur HA est limité à 255 caractères : un message d'erreur très long peut être refusé.

### Revenir à une version précédente

Les versions publiées sont taguées `vX.Y.Z` sur GitHub (onglet **Tags** du dépôt). Le Supervisor installe
toujours la dernière version de la branche `main`.

1. **Le plus simple** : restaurer la sauvegarde du module prise avant la mise à jour
   (**Paramètres → Système → Sauvegardes**, si « Sauvegarder avant la mise à jour » était coché).
2. **Sinon** : noter la configuration, désinstaller le module, retirer le dépôt, puis l'ajouter de nouveau
   avec la référence du tag : `https://github.com/Frazou1/rseq_calendar#v1.4.2`. Réinstaller et recopier
   la configuration. Pour revenir à la dernière version, rajouter le dépôt sans `#…`.

### Licence

Distribué sous la licence **Apache 2.0** : voir le fichier [LICENSE](LICENSE).

---

## English

### Description

**RSEQ Team Calendar** reads the schedule and standings of one or more teams from the **RSEQ** websites
(Quebec student sports network) and publishes them to Home Assistant as **MQTT sensors** (automatic
*MQTT Discovery*).

Two kinds of pages are supported:

| Site | URL type | How it is read |
|---|---|---|
| **RSEQ-QCA** (new site, 2026-2027 season) | **league** page `https://rseqqca.com/ligue/<id>` | Plain HTML (no browser); the team's games are filtered using `team_name` |
| **diffusion.rseq.ca** (old site) | **team** page `https://diffusion.rseq.ca/Default?Type=Team&TeamId=<id>` | Headless Chromium (Selenium), started only if a team uses this site |

Optionally, the add-on can also add each team's **next game** to a Home Assistant calendar (see
[Calendar events](#calendar-events-optional)).

> The add-on folder in this repository is named `example/` (inherited from the template). Do not rename
> it: that would break existing installations.

### Features

- Several teams in a single add-on (`teams` list), or a single team (legacy `team_url` mode).
- 4 sensors per team: **status**, **next game**, **standings**, **last game**.
- Full team schedule (played and upcoming games) in an attribute, for Lovelace cards.
- League standings (position, GP, W, L, T, PF, PA, AVG, PES, PTS).
- Optional HA calendar event for the next game (no duplicates).
- **Adaptive update rhythm** on game days (every 10 min during a game).

### Installation

1. **Prerequisites**: an MQTT broker (for example the **Mosquitto broker** add-on) and the **MQTT**
   integration set up in Home Assistant.
2. Add the repository: **Settings → Add-ons → Add-on Store → ⋮ (top right) → Repositories**, paste
   `https://github.com/Frazou1/rseq_calendar`, then **Add**. Or click this button:

   [![Add the repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FFrazou1%2Frseq_calendar)
3. Refresh the store, open **RSEQ Team Calendar** and click **Install**.
4. Fill in the **Configuration** tab (see below), then **Start**.
5. Open the **Log** tab: you should see the configured teams, the number of games read and
   "Prochaine mise à jour dans N min" (next update in N min).

### Configuration

| Option | Type | Default | Purpose |
|---|---|---|---|
| `teams` | list | `[]` | Teams to follow. Each item: `name` (required, display name and base of the IDs), `team_url` (required), `team_name` (required for an `rseqqca.com` league page: the team's exact name as shown on the page; accents and case are ignored). |
| `team_url` | string | `""` | Legacy mode, one team. Used only when `teams` is empty; the team is then called `default`. It cannot carry a `team_name`, so it **only works with the old** diffusion.rseq.ca site. |
| `entity_prefix` | string | `rseq` | Prefix of the sensors' unique IDs. |
| `update_interval` | integer (30 to 86400) | `3600` | Normal interval between two reads, in seconds. |
| `mqtt_host` | string | `core-mosquitto` | MQTT broker host. |
| `mqtt_port` | integer | `1883` | MQTT broker port. |
| `mqtt_username` | string | `monuser` | MQTT user. Placeholder value: replace it. When not empty, it is sent to the broker. |
| `mqtt_password` | string | `monpassword` | MQTT password. Placeholder value: replace it. |
| `discovery_prefix` | string | `homeassistant` | Home Assistant MQTT discovery prefix. |
| `ha_url` | string | `http://homeassistant.local:8123` | Home Assistant URL, for calendar events (optional). |
| `ha_token` | string | `""` | Long-lived access token (HA profile → Security). Empty = no calendar event. |
| `ha_calendar_entity` | string | `calendar.rseq_equipes` | Calendar that receives the events. |

Example:

```yaml
entity_prefix: rseq
teams:
  - name: My team
    team_url: https://rseqqca.com/ligue/<id>
    team_name: Team name as shown on the page
  - name: Other team
    team_url: https://diffusion.rseq.ca/Default?Type=Team&TeamId=<id>
team_url: ""
update_interval: 3600
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_username: my_mqtt_user
mqtt_password: my_mqtt_password
discovery_prefix: homeassistant
ha_url: http://homeassistant.local:8123
ha_token: ""
ha_calendar_entity: calendar.rseq_equipes
```

To find `team_name` on an rseqqca.com league page, open the page and copy the team's name exactly as it
appears in the list of games.

### Created entities

For each team, the add-on creates an MQTT device **"RSEQ – &lt;name&gt;"** with 4 sensors. `<slug>` is
`name` in lower case, without accents, other characters replaced by `_` (e.g. `My team` → `my_team`).
Sensor names and states are in French.

| Sensor (display name) | Unique ID | State | Main attributes |
|---|---|---|---|
| RSEQ – Statut (&lt;name&gt;) | `<prefix>_<slug>_status` | `success`, `error: calendrier vide` or `error: <message>` | `team_url`, `last_updated` |
| RSEQ – Prochain match (&lt;name&gt;) | `<prefix>_<slug>_next_game` | `YYYY-MM-DD HH:MM – Visitor @ Home` or `Aucun match à venir` | `team`, `team_url`, `next_game`, `upcoming` (next 5), `matchs` (full sorted schedule), `updated` |
| RSEQ – Classement (&lt;name&gt;) | `<prefix>_<slug>_standings` | `N équipes` | `league` (`RSEQ`), `standings` (list: `pos`, `team`, `MJ`, `V`, `D`, `N`, `PP`, `PC`, `MOY`, `PES`, `PTS`), `updated` |
| RSEQ – Dernier match (&lt;name&gt;) | `<prefix>_<slug>_last_game` | `YYYY-MM-DD HH:MM – Visitor @ Home (score)` or `Aucun match joué` | `team`, `team_url`, `last_game`, `updated` |

Each game (`next_game`, items of `upcoming`, `matchs`, `last_game`) contains: `no`, `jour`, `date`,
`time`, `datetime` (ISO, local time), `visitor`, `home`, `result`, `venue` and, for a league page,
`phase` (section title, e.g. regular season).

The `entity_id` is generated by Home Assistant from the device name and the sensor name. To find it:
**Settings → Devices & services → MQTT → Devices → "RSEQ – &lt;name&gt;"**. The examples below use
`sensor.rseq_my_team_rseq_prochain_match_my_team`: replace it with yours.

MQTT topics: `<discovery_prefix>/sensor/<unique ID>/config`, `/state` and `/attributes` (retained
messages).

#### Calendar events (optional)

When `ha_url`, `ha_token` and `ha_calendar_entity` are set, the add-on calls the **HA script
`script.create_calendar_event`** (`script/turn_on` service) for each team's next game.
**This script is not provided: you must create it.** It receives the variables `calendar_entity`,
`start_date`, `end_date` (start + 2 h), `summary` (`Visitor @ Home (RSEQ)`) and `description`
(`Endroit: … | Résultat: …`). Example, with a writable calendar (e.g. the **Local Calendar** integration):

```yaml
script:
  create_calendar_event:
    alias: Create a calendar event
    mode: queued
    fields:
      calendar_entity: {}
      start_date: {}
      end_date: {}
      summary: {}
      description: {}
    sequence:
      - action: calendar.create_event
        target:
          entity_id: "{{ calendar_entity }}"
        data:
          summary: "{{ summary }}"
          description: "{{ description }}"
          start_date_time: "{{ start_date }}"
          end_date_time: "{{ end_date }}"
```

Only one event is created per next game: the last one created is remembered per team in
`/data/last_events.json`.

### Usage examples

Markdown card listing the upcoming games:

```yaml
type: markdown
title: Upcoming games
content: >
  {% for m in state_attr('sensor.rseq_my_team_rseq_prochain_match_my_team', 'upcoming') or [] %}
  - **{{ m.date }} {{ m.time }}** — {{ m.visitor }} @ {{ m.home }} ({{ m.venue }})
  {% else %}
  No upcoming game.
  {% endfor %}
```

Automation: notification when a new result is published:

```yaml
alias: RSEQ - New result
triggers:
  - trigger: state
    entity_id: sensor.rseq_my_team_rseq_dernier_match_my_team
conditions:
  - condition: template
    value_template: "{{ trigger.from_state is not none and trigger.to_state.state != 'Aucun match joué' }}"
actions:
  - action: notify.notify
    data:
      message: "Result: {{ trigger.to_state.state }}"
```

### Update rhythm

After each read, the add-on computes the delay before the next one (`rythme.py`) from all the games it
read:

- **before a game**: wake up at the start time (if it comes before the normal interval);
- **during a game**: every **10 minutes**, until a result is published (4 h at most);
- **after the game**: **hourly** for **3 hours**;
- **otherwise**: the normal interval (`update_interval`).

The minimum delay is 60 seconds. The log shows it: "Prochaine mise à jour dans N min (reason)".

Persistent files in `/data`: `options.json` (configuration), `last_events.json` (events already
created), `prochain_delai` (computed delay), `rythme_fins.json` (detected end of each game, kept 2 days).

### Troubleshooting

Always start with the add-on's **Log** tab.

| Log message | Likely cause | Fix |
|---|---|---|
| `[ERREUR] Aucune équipe configurée` (the add-on stops) | `teams` and `team_url` are both empty | Add at least one team. |
| `[ERREUR] MQTT: …` | Broker unreachable or wrong credentials | Check `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`. |
| Status `error: team_name requis pour une page de ligue rseqqca.com` | League page without `team_name` (or legacy `team_url` mode) | Use `teams` and fill in `team_name`. |
| Status `error: calendrier vide` and `Aucun match pour « … » — snapshot /share/rseq_last.html écrit` | `team_name` matches no team on the page, or the page changed | Compare `team_name` with the name on the page; the page received is saved to `/share/rseq_last.html`. |
| `Table #CalendarTable non trouvée` / Selenium timeout | Old site slow, changed or down | Try again later; prefer an rseqqca.com page. |
| `Erreur création événement HA … HA event error 401/404` | Invalid token, or missing `script.create_calendar_event` | Create a new long-lived token; create the script (see above). |
| `Rythme adaptatif indisponible` | Delay computation failed | The add-on then waits `update_interval`. |
| Sensor still there after removing a team | MQTT messages are retained | Delete the device in MQTT, or clear the retained topics. |

### Known limitations

- Time zone fixed to `America/Toronto` in the image; the `datetime` attribute is local time without an
  offset.
- On an rseqqca.com league page, only the **first** standings table of the page is read.
- The calendar event only covers the next game, with a fixed 2-hour duration.
- A HA sensor state is limited to 255 characters: a very long error message may be rejected.

### Rolling back to a previous version

Released versions are tagged `vX.Y.Z` on GitHub (the repository's **Tags** tab). The Supervisor always
installs the latest version from the `main` branch.

1. **Easiest**: restore the add-on backup taken before the update (**Settings → System → Backups**, if
   "Back up before updating" was checked).
2. **Otherwise**: write down the configuration, uninstall the add-on, remove the repository, then add it
   again with the tag reference: `https://github.com/Frazou1/rseq_calendar#v1.4.2`. Reinstall and paste
   the configuration back. To return to the latest version, add the repository again without `#…`.

### License

Released under the **Apache 2.0** license: see the [LICENSE](LICENSE) file.
