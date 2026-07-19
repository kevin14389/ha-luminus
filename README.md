# ha-luminus

Système Home Assistant qui calcule **automatiquement, chaque jour**, le prix
et le coût de ton électricité pour le contrat **Luminus Comfy Electricité**
(fixe), à Léglise, province de Luxembourg — réseau **ELIA (transport) + ORES
Luxembourg (distribution)**, régime **prosumer** avec compteur communicant.

> Les tarifs ci-dessous ont été **validés contre un vrai décompte annuel
> Luminus** (01.12.2024 → 30.11.2025), pas seulement contre la fiche
> tarifaire générique — voir "Vérification contre un vrai décompte" plus bas
> pour la méthode et les écarts trouvés.

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

3. Vérifie les 4 entités sources du compteur communicant, référencées dans
   le premier bloc `template:` de `packages/luminus_comfy_electricite.yaml` :
   `sensor.daily_energy_delivered_peak` / `_offpeak` (prélèvement jour/nuit)
   et `sensor.daily_energy_returned_peak` / `_offpeak` (injection jour/nuit).
   Si ces entity_id changent un jour (changement d'intégration, etc.),
   mets-les à jour à cet endroit.
4. Redémarre Home Assistant (nécessaire pour que les nouvelles aides
   `input_number` / `input_boolean` / `input_datetime` apparaissent).
5. Va dans **Paramètres > Appareils et services > Aides** pour vérifier /
   ajuster les valeurs tarifaires (elles sont pré-remplies avec les tarifs de
   la fiche Luminus juillet 2025).

## Entités créées

### Prélèvement et injection combinés (`template`, jour+nuit additionnés)
- `sensor.luminus_prelevement_total` — prélèvement réseau total (kWh)
- `sensor.luminus_injection_totale` — injection réseau totale (kWh)

### Compteurs journaliers/mensuels/annuels (`utility_meter`)
- `sensor.luminus_conso_jour` / `_mois` / `_annee` — prélèvement brut (kWh)
- `sensor.luminus_injection_jour` / `_mois` / `_annee` — injection (kWh)

### Prix et coûts (`template`)
- `sensor.luminus_prix_energie_taxes_ttc` — taux énergie + taxes (c€/kWh),
  s'applique au prélèvement **net**
- `sensor.luminus_prix_reseau_ttc` — taux réseau ELIA+ORES (c€/kWh),
  s'applique au prélèvement **brut**
- `sensor.luminus_prix_kwh_ttc` — somme des deux, taux informatif "tout
  compris" (à utiliser comme "entité de prix" dans le Tableau de bord
  Énergie de Home Assistant si tu veux une estimation simple)
- `sensor.luminus_prix_kwh_eur` — `luminus_prix_kwh_ttc` en EUR/kWh
- `sensor.luminus_conso_nette_jour` — prélèvement − injection du jour (kWh,
  **peut être négatif** un jour très productif)
- `sensor.luminus_cout_fixe_journalier` — quote-part journalière des coûts
  fixes (redevance Luminus + terme fixe GRD), en €
- `sensor.luminus_cout_variable_jour` — coût variable du jour : (net ×
  prix énergie+taxes) + (brut × prix réseau), en €
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
- **Changement de prix programmé** (vérifié chaque heure) : applique
  automatiquement `input_number.luminus_prix_energie_ttc_prochain` à la date
  prévue si `input_boolean.luminus_changement_prix_programme` est activé.
- **Correction manuelle** : sur pression du bouton
  `input_button.luminus_appliquer_correction_manuelle`, ajoute
  `input_number.luminus_correction_manuelle` aux accumulateurs mensuel/
  annuel puis la remet à 0.

## Aides tarifaires modifiables (à adapter quand les tarifs changent)

| Aide | Source | Valeur initiale |
|---|---|---|
| `input_number.luminus_prix_energie_ttc` | Décompte annuel, tarif en vigueur depuis le 23.09.2025 | 18,73 c€/kWh |
| `input_number.luminus_redevance_fixe_annuelle` | Décompte annuel | 65,00 €/an |
| `input_number.luminus_cout_energie_verte` | Décompte annuel, dernier trimestre connu (Q3 2025) | 2,8281 c€/kWh |
| `input_number.ores_cout_reseau_variable` | ELIA + ORES combinés, moyenne réelle du dernier décompte annuel | 17,61 c€/kWh |
| `input_number.ores_terme_fixe_grd` | ORES (décompte annuel) | 13,06 €/an |
| `input_number.taxe_accise_special` | SPF Finances, taux réformé 2025 (décompte annuel) | 4,7480 c€/kWh |
| `input_number.taxe_cotisation_energie` | Région wallonne (décompte annuel) | 0,1927 c€/kWh |
| `input_number.taxe_redevance_raccordement` | Région wallonne (décompte annuel) | 0,0750 c€/kWh |
| `input_number.taux_tva` | TVA électricité (Belgique) | 6 % |
| `input_number.remise_fidelite_12_mois` | Promo Luminus domiciliation | 5 % |
| `input_number.remise_fidelite_24_mois` | Promo Luminus domiciliation | 10 % |
| `input_boolean.luminus_remise_fidelite_active` | À activer si tu payes par domiciliation | Désactivé |
| `input_datetime.luminus_date_debut_contrat` | Date de début de ton contrat Luminus | à ajuster |
| `input_number.luminus_prix_energie_ttc_prochain` | Prochain prix énergie, à programmer à l'avance | 0 (inactif) |
| `input_datetime.luminus_prix_energie_date_effet` | Date d'entrée en vigueur du prochain prix | à ajuster |
| `input_boolean.luminus_changement_prix_programme` | Active le changement de prix programmé | Désactivé |
| `input_number.luminus_correction_manuelle` | Montant (€) à ajouter/retirer manuellement aux totaux | 0 |

## Hypothèses et simplifications

- **Pas de tarif prosumer forfaitaire.** Contrairement à ma première
  version (erreur corrigée après analyse d'un vrai décompte), le tarif
  prosumer (€/kW/an) ne s'applique qu'aux compteurs analogiques inversés.
  Avec un compteur digital, ELIA + ORES facturent le réseau sur le
  prélèvement **brut**, avec un "Ristorno" (remise) pour la production
  décentralisée — un mécanisme trop fin pour être reproduit composante par
  composante. À la place, `ores_cout_reseau_variable` est un taux **moyen
  réel**, calculé une fois par an à partir de ton décompte (voir
  "Vérification contre un vrai décompte"), qui redonne le bon coût annuel
  total.
- **TVA 6 %**, appliquée globalement sur l'énergie (après remise éventuelle)
  + coûts énergie verte + coût réseau + taxes. La redevance fixe annuelle
  Luminus (65 €/an) est déjà TVA incluse sur le décompte et n'est donc pas
  re-majorée.
- **Droit d'accise spécial** : la réforme des accises de 2025 a changé ce
  taux en cours d'année (voir `luminus.be/reforme-accises`) — la valeur
  retenue (4,7480 c€/kWh) est celle constatée sur le dernier décompte, pas
  celle de l'ancienne fiche tarifaire par tranche de consommation.
- **Redevance de raccordement** : appliquée sur l'ensemble de la
  consommation, sans tenir compte de l'exemption réglementaire des 100
  premiers kWh/an (montant negligeable : 0,075 c€/kWh).

## Vérification contre un vrai décompte

La première version de ce système reposait uniquement sur la fiche
tarifaire générique Luminus (destinée aux nouveaux clients), qui a mené à
deux erreurs corrigées après analyse d'un vrai décompte annuel (période
01.12.2024-30.11.2025) :

1. **Un tarif prosumer forfaitaire (434,80 €/an) qui ne s'applique pas à ce
   contrat** — le vrai décompte montre un "Ristorno" (remise, pas un
   forfait) pour la production décentralisée, propre au régime "compteur
   digital + prélèvement brut" (voir ci-dessus).
2. **Les "coûts énergie verte" totalement absents du calcul** (~2,83
   c€/kWh, une ligne bien réelle et non négligeable du décompte).

Méthode utilisée pour `ores_cout_reseau_variable` (le taux combiné
ELIA+ORES) : à partir de la section "Electricité : Détails de votre
montant" du décompte —

```
(Montant à payer pour ELIA + Montant à payer pour ORES Luxembourg
 − total des lignes "Terme Fixe")
 ÷ consommation nette totale (kWh, même base que les lignes Luminus/accise)
 × 100  →  c€/kWh
```

Pour ce décompte : `(300,44 + 823,92 − 13,04) ÷ 6.311,33 × 100 = 17,61 c€/kWh`.

**Limite connue** : comme le ratio prélèvement brut/net dépend de ta
production solaire (donc de la saison), ce taux moyen sous-estime
probablement le coût réseau réel en hiver (peu de solaire, brut ≈ net) et
le surestime un peu en été (forte autoconsommation) — mais il redonne le
bon total sur une année complète, ce qui est cohérent avec l'objectif de ce
système (suivi/estimation, pas facture officielle). Recalcule cette
formule à chaque nouveau décompte annuel pour rester calé sur la réalité.

## Compensation prélèvement / injection

Ton compteur communicant expose deux registres séparés (prélèvement et
injection, chacun avec un sous-registre jour/nuit) — le système additionne
peak+offpeak pour chacun, puis calcule le solde net (prélèvement −
injection) chaque jour.

**Règle appliquée** (ce contrat n'a **aucune compensation d'injection** —
confirmé par Luminus, pas de rachat de l'excédent avant 2030 minimum) :

- **Énergie + taxes** : calculées sur le prélèvement net, **plafonné à
  0**. Une journée où tu injectes plus que tu ne prélèves coûte **0** sur
  cette composante — jamais un montant négatif. Sans compensation
  contractuelle, Luminus n'a aucune obligation de te payer l'excédent, et
  une taxe négative n'a pas de sens (ce serait une subvention, pas une
  taxe).
- **Réseau** (ELIA+ORES) : toujours calculé sur le prélèvement **brut**
  en entier, jamais réduit par l'injection. Tu payes toujours le transport
  de ce que tu tires réellement du réseau.
- **Le coût total du jour ne peut donc jamais descendre en dessous du
  coût réseau + coût fixe** — jamais 0€, jamais négatif, même une journée
  très productive.

Deux exemples concrets :
- **Jour productif** : tu prélèves 5 kWh la nuit, injectes 10 kWh le jour.
  Net = 5 − 10 = −5, plafonné à 0 → énergie+taxes = 0€. Réseau = 5 kWh ×
  prix réseau. Total = coût réseau des 5 kWh prélevés + coût fixe.
- **Jour classique** : tu prélèves 10 kWh, injectes 5 kWh. Net = 10 − 5 =
  5 (positif, pas de plafonnement) → énergie+taxes sur 5 kWh. Réseau sur
  la totalité des 10 kWh prélevés. Total = (5 kWh à prix plein) + (10 kWh
  de réseau) + coût fixe.

`sensor.luminus_conso_nette_jour` reste **non plafonné** et peut afficher
un nombre négatif — c'est volontaire, pour que tu voies ton vrai solde de
production. Ce n'est qu'au moment de calculer le coût que le plafond à 0
s'applique.

**Limite connue** : si Luminus t'accorde un jour une vraie compensation
d'injection (ou si le régime "Injection: variable" s'active en 2030 comme
annoncé), il faudra revoir ce plafonnement — un vrai contrat de rachat
changerait la règle ci-dessus.

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
qui inclut la redevance Luminus et le terme fixe GRD) ne sont pas
rétroactivement recalculés au prorata exact si tu changes leur valeur en
cours de mois — l'écart est généralement minime (ce sont de petits montants
forfaitaires annuels).

### Programmer un changement de prix à l'avance (recommandé)

Pour ne jamais oublier une indexation Luminus (elle doit légalement être
annoncée avec un préavis d'au moins 1 mois pour un contrat fixe), encode-la
dès que tu reçois le courrier :

1. `input_number.luminus_prix_energie_ttc_prochain` → le nouveau prix (c€/kWh, TTC)
2. `input_datetime.luminus_prix_energie_date_effet` → la date d'entrée en vigueur (ex. 15/09)
3. `input_boolean.luminus_changement_prix_programme` → active-le (ON)

Le système vérifie chaque heure si la date est atteinte et bascule
`input_number.luminus_prix_energie_ttc` automatiquement ce jour-là — plus
besoin d'y penser le jour J.

### Si tu l'as quand même encodé en retard (ta question : changement le 15/09,
encodé le 25/09)

Dans ce cas précis, le mécanisme ci-dessus s'applique bien **à partir du
moment où tu l'actives** (donc à partir du 25/09), mais **ne corrige pas
tout seul** les 10 jours (15→24/09) déjà calculés et figés à l'ancien prix
— ni le système "programmé", ni aucun autre mécanisme automatique ne peut
deviner rétroactivement qu'une erreur a eu lieu.

Pour rattraper ces 10 jours :

1. Regarde dans l'historique de `sensor.luminus_conso_nette_jour` (ou les
   statistiques Énergie) le total de kWh nets entre le 15 et le 24/09.
2. Calcule l'écart de prix : (nouveau prix − ancien prix) en EUR/kWh sur
   `sensor.luminus_prix_energie_taxes_ttc` (divisé par 100, avant et
   après) — c'est ce taux-là qui bouge lors d'une indexation Luminus, pas
   le taux réseau.
3. Multiplie les deux : `kWh_nets_manqués × écart_prix` = montant en euros
   (positif si tu as sous-compté, négatif si tu as sur-compté).
4. Entre ce montant dans `input_number.luminus_correction_manuelle`.
5. Appuie sur `input_button.luminus_appliquer_correction_manuelle` : le
   montant est ajouté aux totaux mensuel/annuel, puis la correction se
   remet à 0.

Cet outil reste une **estimation de suivi**, pas ta facture officielle
(celle-ci est calculée par Luminus sur base des index réels) — mais il
permet de garder tes totaux HA cohérents avec la réalité même en cas
d'oubli.

## Exemple de carte Lovelace

```yaml
type: entities
title: Électricité - Luminus
entities:
  - entity: sensor.luminus_conso_jour
    name: Prélèvement du jour
  - entity: sensor.luminus_injection_jour
    name: Injection du jour
  - entity: sensor.luminus_conso_nette_jour
    name: Solde net du jour
  - entity: sensor.luminus_prix_kwh_ttc
    name: Prix actuel (indicatif, TTC)
  - entity: sensor.luminus_cout_total_jour
    name: Coût du jour
  - entity: sensor.luminus_cout_total_mois
    name: Coût du mois (estimé)
  - entity: sensor.luminus_cout_total_annee
    name: Coût de l'année (estimé)
```

## Mise à jour des tarifs

- **Luminus** (prix énergie, redevance fixe, coûts énergie verte) : nouvelle
  fiche tarifaire sur [My Luminus](https://my.luminus.be) en cas
  d'indexation (préavis d'au moins 1 mois pour un contrat fixe), ou plus
  fiable : ton prochain décompte annuel.
- **ELIA + ORES** (`ores_cout_reseau_variable`, `ores_terme_fixe_grd`) :
  recalcule la formule de la section "Vérification contre un vrai
  décompte" à chaque nouveau décompte annuel Luminus — c'est la source la
  plus fiable, plus fiable que les fiches tarifaires génériques.
- **Taxes régionales/fédérales** : revues généralement en janvier par le SPF
  Finances / la Région wallonne, mais vérifie aussi ton décompte annuel (la
  réforme des accises 2025 a changé ce taux en cours d'année, en dehors du
  cycle habituel de janvier).

Dans tous les cas, il suffit de mettre à jour les `input_number`
correspondants depuis l'interface Home Assistant — aucune modification de
YAML n'est nécessaire.
