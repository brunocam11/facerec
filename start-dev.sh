#!/bin/bash
watchmedo auto-restart --directory=./app --pattern=*.py --recursive -- python -m app.sqs.indexing_consumer.main 