# n-grams

Download the raw n-gram files:
```bash
wget 'https://kth.box.com/shared/static/v8vr2gve939thzph0zlrbz6p6hfb63xr.xz' -O coca_ngrams_w.tar.xz
tar xvf coca_ngrams_w.tar.xz -C raw/
```

Process the raw files to extract n-grams containing predicates from VRD:
```bash
PREDICATES_PATH='../vrd/predicates.txt'
TOP_K=10

for NGRAM in 2 3 4 5; do
  NGRAMS_PATH="raw/coca_ngrams_x${NGRAM}w.txt"
  mkdir -p "processed/${NGRAM}gram"

  while IFS='' read -r PREDICATE; do
    DEST_PATH="processed/${NGRAM}gram/$(echo "${PREDICATE}" | tr ' ' '_').txt"
    echo "${PREDICATE}" "${DEST_PATH}"
    (
      tr '\t' ' ' |
        grep --word-regexp "${PREDICATE}" |
        sort --reverse --numeric-sort --key 1 |
        head -n "${TOP_K}" |
        tee "${DEST_PATH}"
    ) < "${NGRAMS_PATH}"
    echo
  done < "${PREDICATES_PATH}"

done

```

The resulting file structure should be:
```
data/ngrams
├── processed
│   ├── 2gram
│   │   ├── above.txt
│   │   ├── ...
│   │   └── with.txt
│   ├── 3gram
│   │   ├── above.txt
│   │   ├── ...
│   │   └── with.txt
│   ├── 4gram
│   │   ├── above.txt
│   │   ├── ...
│   │   └── with.txt
│   └── 5gram
│       ├── above.txt
│       ├── ...
│       └── with.txt
└── raw
    ├── coca_ngrams_x2w.txt
    ├── coca_ngrams_x3w.txt
    ├── coca_ngrams_x4w.txt
    └── coca_ngrams_x5w.txt
```