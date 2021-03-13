#!/usr/bin/env bash

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
