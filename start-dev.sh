#!/bin/bash
watchmedo auto-restart --directory=./app --pattern=*.py --recursive -- python -m app.consumers.indexing_consumer.main 