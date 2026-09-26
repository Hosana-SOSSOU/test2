# Local Intelligent PDF Organizer for Linux 🐧📄

Système local-first, offline-capable, modulaire, explicable et strictement réversible pour analyser, classifier, dédupliquer et organiser automatiquement de grandes collections de documents PDF sur Linux.

---

## 📑 Table des Matières

1. [Philosophie & Principes Fondamentaux](#-philosophie--principes-fondamentaux)
2. [Architecture du Code](#-architecture-du-code)
3. [Installation & Dépendances](#-installation--dépendances)
4. [Configuration & Taxonomie Dynamique](#-configuration--taxonomie-dynamique)
5. [Pipeline & Guide d'Utilisation CLI](#-pipeline--guide-dutilisation-cli)
6. [Garanties de Sécurité Filesystem](#-garanties-de-sécurité-filesystem)
7. [Moteur OCR Local & Cache](#-moteur-ocr-local--cache)
8. [Intégration LLM Local (Ollama & llama.cpp)](#-intégration-llm-local-ollama--llamacpp)
9. [Détection des Doublons (SHA-256)](#-détection-des-doublons-sha-256)
10. [Journalisation & Rollback Sécurisé](#-journalisation--rollback-sécurisé)
11. [Suite de Tests](#-suite-de-tests)

---

## 🔒 Philosophie & Principes Fondamentaux

- **Zero Cloud / Zero API Externe** : Aucun appel vers OpenAI, Gemini, Anthropic, HuggingFace ou un OCR SaaS. Toutes les données personnelles restent sur le disque local de la machine Linux.
- **Séparation Stricte Analyse vs Mutation** : La phase d'analyse (`scan`, `classify`, `plan`) ne touche jamais à l'arborescence des fichiers.
- **Simulation d'Abord** : Le mode `simulate` exécute un contrôle complet de pré-vol (existence, permissions, collisions, cross-filesystem, intégrité hash) sans rien modifier.
- **Règle Absolue : NEVER OVERWRITE** : Aucun fichier existant n'est jamais écrasé par inadvertance.
- **Réversibilité Totale (Rollback)** : Chaque déplacement réussi est journalisé dans `operations.json`. La commande `undo` vérifie l'intégrité SHA-256 avant de restaurer les fichiers à leur emplacement d'origine.
- **Explicabilité** : Les classifications ne sont pas des boîtes noires. Elles fournissent les preuves textuelles (`evidence`), le raisonnement (`reason`) et un score heuristique déterministe (`0.0` à `1.0`).

---

## 🏗 Architecture du Code

Le projet adopte le standard Python moderne *src-layout* :

```
src/pdf_organizer/
├── __init__.py                # Métadonnées du package
├── cli.py                     # Interface CLI (argparse avec 10 sous-commandes)
├── models.py                  # Dataclasses strictes (Document, Classification, MovePlan, OperationLog)
├── config.py                  # Chargement et validation de config.yaml
├── taxonomy.py                # Chargement dynamique de la taxonomie arborescente (taxonomy.yaml)
├── scanner.py                 # Découverte récursive des PDFs (.pdf, .PDF, gestion symlinks)
├── metadata.py                # Extraction métadonnées filesystem et objets PDF
├── extractor.py               # Extraction de texte et détection de qualité (seuil OCR)
├── hashing.py                 # Calcul cryptographique de l'empreinte SHA-256 (streaming par blocs)
├── duplicates.py              # Détection des doublons exacts par hash
├── planner.py                 # Traduction des classifications en MovePlan concrets
├── simulator.py               # Moteur de simulation en lecture seule (dry-run complet)
├── mover.py                   # Déplacement physique avec politique NEVER OVERWRITE et cross-fs
├── undo.py                    # Moteur de rollback sécurisé avec vérification SHA-256
├── reports.py                 # Génération des rapports (report.csv, report.json, report.md)
├── review.py                  # Visualiseur et inspecteur de rapports pour l'utilisateur
├── ocr/
│   ├── __init__.py
│   ├── base.py                # Protocole OCRBackend, OCRResult et OCRCache persistant
│   └── tesseract.py           # Backend Tesseract local (rendu de page + subprocess)
├── classification/
│   ├── __init__.py
│   ├── base.py                # Protocole Classifier
│   ├── rule_based.py          # Classifieur déterministe à scores pondérés et mots-clés
│   └── local_llm.py           # Classifieur LLM local avec validation JSON et fallback
└── llm/
    ├── __init__.py
    ├── base.py                # Protocole LocalLLM et exceptions
    ├── ollama.py              # Client HTTP ultra-léger pour daemon Ollama local
    └── llamacpp.py            # Client HTTP pour serveur local llama.cpp / vLLM
```

---

## 📦 Installation & Dépendances

### 1. Prérequis Système (Debian / Ubuntu / Fedora / Arch)

```bash
# Python 3.10+ et outils de base
sudo apt update
sudo apt install python3 python3-pip

# Moteur OCR local Tesseract (optionnel mais recommandé pour les scans)
sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
```

### 2. Installation de l'environnement Python

Le projet est conçu pour minimiser les dépendances superflues :
- `PyYAML` : pour la lecture des fichiers YAML (un parseur natif de secours est également intégré dans `config.py`).
- `PyMuPDF` (`fitz`) : pour l'extraction ultra-rapide de texte et le rendu vectoriel des pages PDF.

```bash
# Dans le dossier du projet :
pip install -e .

# Ou installer avec les extras optionnels :
pip install -e ".[ocr,dev]"
```

Après installation, la commande `pdf-organizer` est disponible directement dans votre terminal. Vous pouvez aussi utiliser l'exécutable local `./pdf-organizer`.

---

## ⚙️ Configuration & Taxonomie Dynamique

### `config/config.yaml`

```yaml
classification:
  backend: rule_based             # "rule_based" ou "local_llm"
  manual_review_threshold: 0.50   # Tout score < 0.50 est dirigé vers "À_classer"
  default_unclassified_category: À_classer
  taxonomy_path: config/taxonomy.yaml

ocr:
  enabled: true
  backend: tesseract
  min_text_len_per_page: 30       # Moins de 30 caractères par page = document OCR_REQUIRED
  lang: fra+eng
  tesseract_cmd: tesseract
  cache_dir: .pdf_organizer_cache/ocr

llm:
  enabled: false                  # Désactivé par défaut (rule-based pur)
  backend: ollama                 # "ollama" ou "llamacpp"
  model: llama3.2
  endpoint: http://127.0.0.1:11434
  timeout_seconds: 30
  fallback_to_rule_based: true

safety:
  overwrite: false                # Règle absolue : aucun écrasement automatique
  require_confirmation: true      # Exige confirmation interactive ou --yes
  collision_strategy: RENAME      # "RENAME" (ajoute _1, _2), "SKIP", ou "REVIEW"
  destination_base_dir: null      # Optionnel : restreint la destination à une racine autorisée
```

### `config/taxonomy.yaml`

La taxonomie est **100% dynamique**. L'ajout d'une nouvelle catégorie (ex: `Sciences/Astronomie`) dans le fichier YAML est immédiatement pris en compte sans modifier une seule ligne de code Python :

```yaml
Maths:
  Algèbre:
    keywords: ["eigenvalue", "vector space", "matrix", "linear algebra", "matrice"]
  Analyse:
    keywords: ["calculus", "integral", "derivative", "differential equation"]

Informatique:
  Intelligence-Artificielle:
    keywords: ["neural network", "deep learning", "cnn", "transformer", "backpropagation"]
  Programmation:
    keywords: ["python", "rust", "c++", "compilateur", "algorithm"]

Physique:
  keywords: ["thermodynamics", "entropy", "quantum mechanics"]

À_classer:
  keywords: []
```

---

## 🚀 Pipeline & Guide d'Utilisation CLI

Le cycle de vie complet garantit qu'aucune action sur le disque n'a lieu avant votre accord explicite.

```
scan  ──►  inventory  ──►  ocr (optionnel)  ──►  classify  ──►  plan  ──►  review  ──►  simulate  ──►  apply  ──►  (undo)
```

### 1. `pdf-organizer scan` : Découverte et inventaire

Analyse les répertoires spécifiés, extrait les métadonnées et le texte, et détecte les doublons sans déplacer aucun fichier.

```bash
./pdf-organizer scan ~/Downloads ~/Documents/Vrac --output-dir reports/
```

Génère automatiquement :
- `reports/report.json` : base de données complète structurée.
- `reports/report.csv` : tableur exploitable (LibreOffice Calc, Excel, Pandas).
- `reports/report.md` : rapport lisible avec indicateurs synthétiques.

### 2. `pdf-organizer ocr` : Traitement séparé des scans

Traite uniquement les documents ayant le statut `OCR_REQUIRED`. Utilise le cache local basé sur le hash pour ne jamais retraiter inutilement le même document.

```bash
./pdf-organizer ocr reports/report.json --lang fra+eng --output-dir reports/
```

### 3. `pdf-organizer classify` : Classification des documents

Attribue une catégorie et un score heuristique d'explicabilité à chaque document.

```bash
# Avec le moteur déterministe rule-based :
./pdf-organizer classify reports/report.json --backend rule_based

# Ou avec un LLM local (Ollama) :
./pdf-organizer classify reports/report.json --backend local_llm
```

### 4. `pdf-organizer plan` : Élaboration du plan de destination

Calcule les chemins cibles vers le répertoire d'organisation sans déplacer aucun fichier.

```bash
./pdf-organizer plan reports/report.json ~/Documents/Bibliotheque
```

### 5. `pdf-organizer review` : Inspection interactive du plan

Affiche la synthèse, les cas nécessitant une revue humaine (`À_classer` ou scores ambigus) et les collisions détectées.

```bash
# Résumé global
./pdf-organizer review reports/report.json

# Uniquement les documents nécessitant une revue
./pdf-organizer review reports/report.json --needs-review

# Afficher les groupes de doublons exacts
./pdf-organizer review reports/report.json --show-duplicates
```

### 6. `pdf-organizer simulate` : Simulation officielle (Dry-Run)

Vérifie l'existence des sources, la lisibilité, l'intégrité SHA-256, les permissions de destination, le même filesystem vs cross-filesystem.

```bash
./pdf-organizer simulate reports/report.json
```

Exemple de sortie :
```
===========================================================
                 SIMULATION REPORT (DRY RUN)               
===========================================================
Total evaluated files:   15
Ready to move:           12
Potential collisions:    1
Requires manual review:  2
Already in position:     0
Permission / I/O errors: 0
-----------------------------------------------------------
1. [WOULD_MOVE] deep_learning.pdf
   FROM:     /home/user/Downloads/deep_learning.pdf
   TO:       /home/user/Documents/Bibliotheque/Informatique/Intelligence-Artificielle/deep_learning.pdf
   CATEGORY: Informatique/Intelligence-Artificielle (Score: 0.94)

2. [COLLISION] linear_algebra.pdf
   FROM:     /home/user/Downloads/linear_algebra.pdf
   TO:       /home/user/Documents/Bibliotheque/Maths/Algèbre/linear_algebra.pdf
   CATEGORY: Maths/Algèbre (Score: 0.88)
   NOTE:     A file already exists at the destination path.

STATUS: SAFE. No filesystem modifications were performed.
===========================================================
```

### 7. `pdf-organizer apply` : Déplacement physique contrôlé

Exécute les déplacements approuvés. Exige une confirmation explicite (ou le flag `--yes`).

```bash
./pdf-organizer apply reports/report.json --journal operations.json --yes
```

### 8. `pdf-organizer undo` : Rollback intégral

Permet d'annuler les déplacements en cas d'erreur. Vérifie que chaque fichier correspond exactement à son empreinte SHA-256 avant de le remettre à sa place d'origine.

```bash
./pdf-organizer undo --journal operations.json
```

### 9. `pdf-organizer duplicates` : Détection directe des doublons

```bash
./pdf-organizer duplicates ~/Documents ~/Downloads
```

### 10. `pdf-organizer process` : Pipeline en une seule étape sécurisée

Exécute scan + classification + plan + rapports sans jamais toucher au filesystem :

```bash
./pdf-organizer process ~/Downloads ~/Bureau --target-dir ~/Documents/Organise --output-dir reports/
```

---

## 🛡 Garanties de Sécurité Filesystem

1. **Règle NEVER OVERWRITE** : Si le fichier de destination existe déjà, le moteur ne l'écrase jamais. Selon la stratégie configurée (`RENAME`, `SKIP`, `REVIEW`), il renomme le nouveau fichier en `nom_1.pdf` ou ignore l'opération.
2. **Détection Cross-Filesystem** :
   - *Même filesystem* (`source.stat().st_dev == dest.stat().st_dev`) : opération atomique via `os.replace`.
   - *Filesystems différents* : copie complète (`shutil.copy2`) ➔ synchronisation physique (`os.fsync`) ➔ vérification rigoureuse de l'empreinte SHA-256 ➔ suppression de la source **uniquement après succès validé**.
3. **Protection contre les Modifications Intempestives** : Avant tout déplacement ou rollback, le fichier source est re-haché à la volée. Si le hash a changé depuis le scan, l'opération est avortée.
4. **Jail de Répertoire** : Si `destination_base_dir` est défini dans la configuration, aucune tentative de déplacement en dehors de ce dossier (ex: injection de `../`) ne peut être exécutée.

---

## 🤖 Intégration LLM Local (Ollama & llama.cpp)

Pour les utilisateurs disposant d'un modèle local, l'abstraction `LocalLLM` permet d'exploiter un modèle open-source sans aucune API distante :

### Utilisation avec Ollama

1. Démarrer Ollama localement :
   ```bash
   ollama run llama3.2
   ```
2. Activer dans `config/config.yaml` :
   ```yaml
   llm:
     enabled: true
     backend: ollama
     model: llama3.2
     endpoint: http://127.0.0.1:11434
     timeout_seconds: 30
   ```
3. L'application envoie un prompt ultra-concis (titre, auteur, extrait de texte de 1 500 caractères, liste des catégories autorisées) et contraint la sortie en JSON strict :
   ```json
   {
     "category": "Informatique/Intelligence-Artificielle",
     "score": 0.92,
     "evidence": ["deep learning", "neural network"],
     "reason": "Document discusses deep learning and neural network training."
   }
   ```
4. **Validation Stricte** : Si le daemon est indisponible, si le JSON est invalide ou si la catégorie n'existe pas dans la taxonomie, le classifieur bascule automatiquement sur le `RuleBasedClassifier` de secours.

---

## 🧪 Suite de Tests

La suite de tests couvre l'ensemble des modules critiques et utilise exclusivement des répertoires temporaires (`tempfile`) :

```bash
# Exécution avec unittest (intégré à Python standard) :
python3 -m unittest discover tests

# Ou avec pytest si installé :
pytest -v
```

Les 10 axes testés :
1. `test_scanner.py` : Découverte récursive, extensions `.pdf`/`.PDF`, exclusion des non-PDFs, répertoires absents, symlinks.
2. `test_metadata.py` : Taille, date de modification, métadonnées PDF, nombre de pages, titre, auteur.
3. `test_extractor.py` : PDF textuel, PDF vide, PDF nécessitant OCR, PDF corrompu.
4. `test_ocr.py` : Absence de binaire Tesseract, exécution OCR, échec contrôlé, cache disque par SHA-256.
5. `test_classification.py` : Mots-clés, scores bornés `[0.0, 1.0]`, routage vers `À_classer`, fallback LLM vers rule-based.
6. `test_duplicates.py` : Doublons exacts SHA-256, noms distincts, groupes multiples, aucune suppression automatique.
7. `test_planner.py` : Construction des chemins cibles, détection des collisions, cas `SAME_LOCATION`.
8. `test_simulator.py` : Garantie formelle de non-mutation du filesystem pendant la simulation.
9. `test_mover.py` : Déplacement standard, politique NEVER OVERWRITE avec renommage `_1.pdf`, vérification de hash, journalisation.
10. `test_undo.py` : Restauration fidèle, avortement si le fichier destination a été altéré, préservation des fichiers sources occupés.

---

## 📄 Licence

Ce projet est distribué sous licence MIT. Développé pour la communauté Linux soucieuse de la confidentialité de ses documents.
