# Face Recognition CLI Tools

This directory contains command-line tools for the face recognition system.

## Available Tools

### Face Matching Streamlit App

A Streamlit app for testing face matching functionality.

```bash
poetry run python -m app.cli.face_matching_app
```

### S3 Album Indexer

Index faces from images in an S3 album into a Pinecone collection.

```bash
poetry run python -m app.cli.index_s3_album --bucket <bucket_name> --album <album_id> --collection <collection_id>
```

Arguments:
- `--bucket`: S3 bucket name (required)
- `--album`: Album ID in S3 (required)
- `--collection`: Collection ID to index into (required)
- `--prefix`: S3 prefix to prepend to album ID (optional)
- `--max-images`: Maximum number of images to process (default: 100)
- `--max-faces`: Maximum number of faces to detect per image (default: 1)

### Face Matching Accuracy Testing

Test the accuracy of the face matching system using images directly from S3.

```bash
poetry run python -m app.cli.test_face_matching --bucket <bucket_name> --prefix <prefix> --output <output_file>
```

Arguments:
- `--bucket`: S3 bucket name (required)
- `--prefix`: S3 prefix to filter by (optional)
- `--collection-id`: Collection ID to use for testing (default: "test_collection")
- `--threshold`: Similarity threshold (default: 0.7)
- `--max-matches`: Maximum number of matches to return (default: 10)
- `--max-albums`: Maximum number of albums to test (default: 10)
- `--max-images`: Maximum number of images per album (default: 5)
- `--output`: Output file for test results (default: "test_results.json")

### Results Visualization

Visualize the results of face matching accuracy tests.

```bash
poetry run python -m app.cli.visualize_results --results <results_file> --output <output_dir>
```

Arguments:
- `--results`: Path to test results JSON file (required)
- `--output`: Directory to save visualizations (default: "visualizations")
- `--max-visualizations`: Maximum number of visualizations to create (default: 50)

## Example Workflow

1. Index faces from an S3 album:
   ```bash
   poetry run python -m app.cli.index_s3_album --bucket my-bucket --album family-photos --collection family
   ```

2. Run accuracy tests:
   ```bash
   poetry run python -m app.cli.test_face_matching --bucket my-bucket --prefix test-photos --output test_results.json
   ```

3. Visualize test results:
   ```bash
   poetry run python -m app.cli.visualize_results --results test_results.json --output visualizations
   ```

4. Run the Streamlit app:
   ```bash
   poetry run python -m app.cli.face_matching_app
   ```

## Notes

- The accuracy testing process works directly with S3 images without local downloads.
- The system assumes that S3 albums are organized as directories (prefixes) in the bucket.
- Images are expected to be in common formats (jpg, jpeg, png). 