#!/bin/bash
# Package Lambda function for deployment
# This script creates a deployment-ready ZIP package for the People Count API Lambda function

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAMBDA_NAME="${1:-people_count_api}"
OUTPUT_DIR="${2:-$PROJECT_ROOT/build}"

echo "Packaging Lambda function: $LAMBDA_NAME"
echo "Output directory: $OUTPUT_DIR"

# Create build directory
mkdir -p "$OUTPUT_DIR"
BUILD_DIR="$OUTPUT_DIR/${LAMBDA_NAME}_build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Install dependencies
echo "Installing dependencies..."
pip install -r "$PROJECT_ROOT/src/lambdas/requirements.txt" -t "$BUILD_DIR" --quiet

# Copy Lambda handler
echo "Copying Lambda handler..."
cp "$PROJECT_ROOT/src/lambdas/${LAMBDA_NAME}.py" "$BUILD_DIR/"

# Copy common modules (not needed for authorizers)
if [[ "$LAMBDA_NAME" != "authorizer_rest" && "$LAMBDA_NAME" != "authorizer_websocket" ]]; then
    echo "Copying common modules..."
    mkdir -p "$BUILD_DIR/common"
    cp "$PROJECT_ROOT/src/common/__init__.py" "$BUILD_DIR/common/"
    cp "$PROJECT_ROOT/src/common/timestream_client.py" "$BUILD_DIR/common/"
    cp "$PROJECT_ROOT/src/common/models.py" "$BUILD_DIR/common/"
fi

# Create ZIP package
echo "Creating ZIP package..."
cd "$BUILD_DIR"
zip -r "$OUTPUT_DIR/${LAMBDA_NAME}.zip" . -q

# Cleanup
cd "$PROJECT_ROOT"
rm -rf "$BUILD_DIR"

echo "✓ Package created: $OUTPUT_DIR/${LAMBDA_NAME}.zip"
echo "  Size: $(du -h "$OUTPUT_DIR/${LAMBDA_NAME}.zip" | cut -f1)"
