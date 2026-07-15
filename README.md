# ha-luminus

Système Home Assistant qui calcule **automatiquement, chaque jour**, le prix
et le coût de ton électricité pour le contrat **Luminus Comfy Electricité**
(fixe), à Léglise, province de Luxembourg — réseau **ORES Luxembourg**,
régime **prosumer** avec compteur communicant.

Toute la tarification (prix de l'énergie, coûts réseau ORES, taxes, TVA,
remises de fidélité) est exposée sous forme d'aides (`input_number` /
`input_boolean` / `input_datetime`) modifiables **depuis l'interface Home
Assistant**, sans toucher au YAML — pratique pour les adaptations de prix en
cours d'année (indexation Luminus, nouveaux tarifs ORES au 1er janvier, etc.).

## Installation

1. Copie le dossier `packages/` de ce repo dans ton dossier de configuration
   Home Assistant (à côté de `configuration.yaml`).
2. Dans `configuration.yaml`, assure-toi que les packages sont chargés :

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. Vérifie l'entité source de consommation dans
   `packages/luminus_comfy_electricite.yaml` (section `utility_meter`) :
   elle est actuellement réglée sur `sensor.daily_energy_delivered_peak`
   (ton capteur de consommation nette du compteur communicant). Si cette
   entity_id change un jour (changement d'intégration, etc.), mets à jour
   les 3 occurrences dans le fichier.
4. Redémarre Home Assistant (nécessaire pour que les nouvelles aides
   `input_number` / `input_boolean` / `input_datetime` apparaissent).
5. Va dans **Paramètres > Appareils et services > Aides** pour vérifier /
   ajuster les valeurs tarifaires (elles sont pré-remplies avec les tarifs de
   la fiche Luminus juillet 2025).

## Entités créées

### Compteurs de consommation (`utility_meter`)
- `sensor.luminus_conso_jour` — consommation nette du jour (kWh)
- `sensor.luminus_conso_mois` — consommation nette du mois (kWh)
- `sensor.luminus_conso_annee` — consommation nette de l'année (kWh)

### Prix et coûts (`template`)
- `sensor.luminus_prix_kwh_ttc` — prix tout compris (énergie + réseau +
  taxes + TVA) en c€/kWh
- `sensor.luminus_prix_kwh_eur` — le même prix en EUR/kWh (à utiliser comme
  "entité de prix" dans le Tableau de bord Énergie de Home Assistant)
- `sensor.luminus_cout_fixe_journalier` — quote-part journalière des coûts
  fixes (redevance Luminus + terme fixe GRD + tarif prosumer), en €
- `sensor.luminus_cout_variable_jour` — coût variable du jour (conso ×
  prix), en €
- `sensor.luminus_cout_total_jour` — coût total du jour (variable + fixe), en €
- `sensor.luminus_cout_total_mois` / `sensor.luminus_cout_total_annee` —
  total réel cumulé du mois / de l'année en cours (voir "Changement de tarif
  en cours d'année" ci-dessous)

### Automations
- **Résumé quotidien** (23h55) : notification persistante avec le
  récapitulatif du jour, et ajout du coût du jour aux accumulateurs
  mensuel/annuel (`input_number.luminus_cout_accumulateur_mois` /
  `_annee`, entités internes à ne pas modifier à la main).
- **Reset mensuel** (00h01 le 1er du mois) et **reset annuel** (00h02 le
  1er janvier) : remettent les accumulateurs à 0 pour démarrer la nouvelle
  période.

## Aides tarifaires modifiables (à adapter quand les tarifs changent)

| Aide | Source | Valeur initiale |
|---|---|---|
| `input_number.luminus_prix_energie_ttc` | Fiche tarifaire Luminus, "Énergie fournie" | 18,73 c€/kWh |
| `input_number.luminus_redevance_fixe_annuelle` | Fiche tarifaire Luminus | 65,00 €/an |
| `input_number.ores_cout_distribution` | ORES Luxembourg, compteur mono-horaire | 10,79 c€/kWh |
| `input_number.ores_cout_transport` | ORES | 2,98 c€/kWh |
| `input_number.ores_terme_fixe_grd` | ORES | 13,84 €/an |
| `input_number.ores_tarif_prosumer` | ORES Luxembourg | 86,96 €/kW/an |
| `input_number.ores_puissance_onduleur` | Puissance de ton onduleur PV | 5 kW |
| `input_number.taxe_accise_special` | SPF Finances (valable jusqu'à 20.000 kWh/an) | 5,0329 c€/kWh |
| `input_number.taxe_cotisation_energie` | Région wallonne | 0,2042 c€/kWh |
| `input_number.taxe_redevance_raccordement` | Région wallonne | 0,0750 c€/kWh |
| `input_number.taux_tva` | TVA électricité (Belgique) | 6 % |
| `input_number.remise_fidelite_12_mois` | Promo Luminus domiciliation | 5 % |
| `input_number.remise_fidelite_24_mois` | Promo Luminus domiciliation | 10 % |
| `input_boolean.luminus_remise_fidelite_active` | À activer si tu payes par domiciliation | Désactivé |
| `input_datetime.luminus_date_debut_contrat` | Date de début de ton contrat Luminus | à ajuster |

## Hypothèses et simplifications

- **Pas de compensation d'injection variable** : en régime prosumer avec
  compteur communicant, la production PV est nettée directement par le
  compteur (comme un "compteur qui tourne à l'envers" virtuel) — il n'y a
  donc pas de formule Belpex à suivre. Le coût de l'usage du réseau lié à
  l'injection est couvert par le **tarif prosumer** forfaitaire (€/kW/an).
- **TVA 6 %**, appliquée globalement sur l'énergie (après remise éventuelle)
  + coûts réseau + taxes. La redevance fixe annuelle Luminus (65 €/an) est
  déjà TVA incluse sur la fiche tarifaire et n'est donc pas re-majorée.
- **Droit d'accise spécial** : le taux retenu (5,0329 c€/kWh) est celui
  valable jusqu'à 20.000 kWh/an de consommation ; au-delà (peu probable pour
  un ménage), il descend à 4,8188 c€/kWh — à ajuster manuellement si
  pertinent.
- **Redevance de raccordement** : appliquée sur l'ensemble de la
  consommation, sans tenir compte de l'exemption réglementaire des 100
  premiers kWh/an (montant negligeable : 0,075 c€/kWh).

## Changement de tarif en cours d'année (ex. indexation Luminus en septembre)

Le système gère ça correctement, sans rien recalculer manuellement :

- Chaque jour, `sensor.luminus_cout_total_jour` est calculé avec le prix en
  vigueur **ce jour-là**, puis figé le soir (23h55) dans les accumulateurs
  mensuel/annuel.
- Si tu changes `input_number.luminus_prix_energie_ttc` (ou n'importe quel
  autre tarif) en cours de mois, seuls les jours **suivant** le changement
  utilisent le nouveau prix. Les jours précédents restent comptabilisés au
  prix d'avant, aussi bien dans l'historique de `sensor.luminus_cout_total_jour`
  que dans les totaux mensuel/annuel.
- Exemple concret : si tu modifies le prix le 15 septembre, le total du mois
  de septembre (`sensor.luminus_cout_total_mois`) sera la somme des 14
  premiers jours à l'ancien prix + les jours suivants au nouveau prix — pas
  le nouveau prix appliqué à tout le mois.

Seule limite : les coûts fixes journaliers (`sensor.luminus_cout_fixe_journalier`,
qui inclut la redevance Luminus, le terme fixe GRD et le tarif prosumer) ne
sont pas rétroactivement recalculés au prorata exact si tu changes leur
valeur en cours de mois — l'écart est généralement minime (ce sont de petits
montants forfaitaires annuels).

## Exemple de carte Lovelace

```yaml
type: entities
title: Électricité - Luminus
entities:
  - entity: sensor.luminus_conso_jour
    name: Consommation du jour
  - entity: sensor.luminus_prix_kwh_ttc
    name: Prix actuel (TTC)
  - entity: sensor.luminus_cout_total_jour
    name: Coût du jour
  - entity: sensor.luminus_cout_total_mois
    name: Coût du mois (estimé)
  - entity: sensor.luminus_cout_total_annee
    name: Coût de l'année (estimé)
```

## Mise à jour des tarifs

- **Luminus** (prix énergie, redevance fixe) : nouvelle fiche tarifaire
  disponible sur [My Luminus](https://my.luminus.be) en cas d'indexation
  (préavis d'au moins 1 mois pour un contrat fixe).
- **ORES** (coûts réseau, tarif prosumer) : révisés chaque 1er janvier,
  publiés sur [ores.be](https://www.ores.be).
- **Taxes régionales/fédérales** : revues généralement en janvier par le SPF
  Finances / la Région wallonne.

Dans tous les cas, il suffit de mettre à jour les `input_number`
correspondants depuis l'interface Home Assistant — aucune modification de
YAML n'est nécessaire.
