#!/bin/bash

# monitor_worker.sh - Script to monitor worker performance during large-scale testing
# Usage: ./monitor_worker.sh [container_name] [output_dir]

CONTAINER=${1:-facerec-worker-dev}
OUTPUT_DIR=${2:-./metrics}
INTERVAL=10  # seconds between snapshots

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo "Monitoring container: $CONTAINER"
echo "Saving metrics to: $OUTPUT_DIR"
echo "Press Ctrl+C to stop monitoring"

# Timestamp for this monitoring session
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
STATS_FILE="$OUTPUT_DIR/stats_$TIMESTAMP.csv"
MEMORY_FILE="$OUTPUT_DIR/memory_$TIMESTAMP.csv"
SUMMARY_FILE="$OUTPUT_DIR/summary_$TIMESTAMP.txt"

# Initialize stats file with headers
echo "timestamp,cpu_percent,memory_usage_mb,memory_limit_mb,memory_percent,processed_total,success_count,faces_found,no_faces,errors" > "$STATS_FILE"
echo "timestamp,memory_mb" > "$MEMORY_FILE"

# Get startup metrics
START_TIME=$(date +%s)

# Initialize counter
counter=0

# Function to extract metrics from worker logs
extract_metrics() {
    processed=$(docker logs $CONTAINER 2>&1 | grep -c "Successfully processed job")
    success=$(docker logs $CONTAINER 2>&1 | grep -c "Successfully processed job")
    faces_count=$(docker logs $CONTAINER 2>&1 | grep -c "found [1-9]")
    no_faces=$(docker logs $CONTAINER 2>&1 | grep -c "No faces detected")
    errors=$(docker logs $CONTAINER 2>&1 | grep -c "Error in Ray actor")
    
    echo "$processed,$success,$faces_count,$no_faces,$errors"
}

# Main monitoring loop
while true; do
    # Get current timestamp
    now=$(date +"%Y-%m-%d %H:%M:%S")
    seconds_elapsed=$(($(date +%s) - START_TIME))
    
    # Get container stats (CPU %, Memory usage, Memory limit)
    stats=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}" $CONTAINER 2>/dev/null)
    
    if [ -z "$stats" ]; then
        echo "Container $CONTAINER not found or not running!"
        break
    fi
    
    # Parse memory usage
    cpu_percent=$(echo $stats | cut -d',' -f1 | sed 's/%//')
    memory_usage=$(echo $stats | cut -d',' -f2 | cut -d'/' -f1 | sed 's/MiB//' | sed 's/GiB/*1024/' | bc)
    memory_limit=$(echo $stats | cut -d',' -f2 | cut -d'/' -f2 | sed 's/MiB//' | sed 's/GiB/*1024/' | bc)
    memory_percent=$(echo $stats | cut -d',' -f3 | sed 's/%//')
    
    # Extract processing metrics
    processing_metrics=$(extract_metrics)
    
    # Save to CSV
    echo "$now,$cpu_percent,$memory_usage,$memory_limit,$memory_percent,$processing_metrics" >> "$STATS_FILE"
    echo "$seconds_elapsed,$memory_usage" >> "$MEMORY_FILE"
    
    # Print status
    counter=$((counter + 1))
    if [ $((counter % 6)) -eq 0 ]; then  # Print header every minute
        echo "-------------------------------------------------------------------------------------------------"
        echo "TIME     | CPU% | MEMORY  | PROCESSED | SUCCESS | FACES | NO FACES | ERRORS"
        echo "-------------------------------------------------------------------------------------------------"
    fi
    
    processed_count=$(echo $processing_metrics | cut -d',' -f1)
    success_count=$(echo $processing_metrics | cut -d',' -f2)
    faces_count=$(echo $processing_metrics | cut -d',' -f3)
    no_faces=$(echo $processing_metrics | cut -d',' -f4)
    errors=$(echo $processing_metrics | cut -d',' -f5)
    
    # Format time as MM:SS
    mins=$((seconds_elapsed / 60))
    secs=$((seconds_elapsed % 60))
    formatted_time=$(printf "%02d:%02d" $mins $secs)
    
    echo "$formatted_time | $cpu_percent% | ${memory_usage}MB | $processed_count | $success_count | $faces_count | $no_faces | $errors"
    
    sleep $INTERVAL
done

# Generate summary report
{
    echo "=== WORKER PERFORMANCE SUMMARY ==="
    echo "Monitoring period: $(date -r $START_TIME "+%Y-%m-%d %H:%M:%S") to $(date "+%Y-%m-%d %H:%M:%S")"
    echo "Duration: $(($seconds_elapsed / 60)) minutes $(($seconds_elapsed % 60)) seconds"
    echo ""
    echo "--- PROCESSING METRICS ---"
    echo "Total jobs processed: $processed_count"
    echo "Successful jobs: $success_count"
    echo "Images with faces: $faces_count"
    echo "Images with no faces: $no_faces"
    echo "Errors: $errors"
    
    # Calculate processing rate
    if [ $seconds_elapsed -gt 0 ]; then
        rate=$(echo "scale=2; $processed_count / $seconds_elapsed" | bc)
        echo "Processing rate: $rate images/second"
        echo "                 $(echo "scale=2; $rate * 60" | bc) images/minute"
        echo "                 $(echo "scale=2; $rate * 3600" | bc) images/hour"
    fi
    
    echo ""
    echo "--- RESOURCE USAGE ---"
    avg_cpu=$(awk -F, '{ sum += $2; n++ } END { if (n > 0) print sum / n; }' "$STATS_FILE")
    avg_memory=$(awk -F, '{ sum += $3; n++ } END { if (n > 0) print sum / n; }' "$STATS_FILE")
    max_memory=$(awk -F, 'BEGIN {max=0} {if ($3>max) max=$3} END {print max}' "$STATS_FILE")
    
    echo "Average CPU usage: ${avg_cpu}%"
    echo "Average memory usage: ${avg_memory}MB"
    echo "Peak memory usage: ${max_memory}MB"
    
    echo ""
    echo "For complete metrics, see:"
    echo "$STATS_FILE"
    
    echo ""
    echo "To generate graphs, run:"
    echo "gnuplot -e \"input_file='$MEMORY_FILE'; output_file='$OUTPUT_DIR/memory_chart_$TIMESTAMP.png'\" memory_chart.gnuplot"
} > "$SUMMARY_FILE"

echo ""
echo "Monitoring stopped. Summary saved to: $SUMMARY_FILE" 