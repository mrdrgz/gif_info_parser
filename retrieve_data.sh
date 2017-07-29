#!/bin/bash

# Retrieve list of files
curl -s 'http://kitten.ga/tags/?text=' | jq -r '.[] | "http://kitten.ga/gifs/\(.id).gif\t\(.name)"' > gif_data.tsv