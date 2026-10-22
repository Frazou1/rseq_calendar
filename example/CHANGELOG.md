<!-- https://developers.home-assistant.io/docs/add-ons/presentation#keeping-a-changelog -->

## 1.4.0

- Nouveau site RSEQ-QCA (saison 2026-2027) : `team_url` peut être une page de ligue
  `https://rseqqca.com/ligue/<id>` ; ajouter alors `team_name` (nom de l'équipe sur la page, ex. « Accueil »).
  Lecture HTML directe, sans navigateur ; mêmes capteurs et mêmes attributs qu'avant (+ `phase`).
- L'ancien site `diffusion.rseq.ca` reste pris en charge (Selenium démarré seulement s'il est utilisé).

## 1.3.1

Remove loop to read 2 event in same date

## 1.3.0
Read icon on calendar and insert into a hotmail calendar

## 1.2.0

- Add an apparmor profile
- Update to 3.15 base image with s6 v3
- Add a sample script to run as service and constrain in aa profile

## 1.1.0

- Updates

## 1.0.0

- Initial release
