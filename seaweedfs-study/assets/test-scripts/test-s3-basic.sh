#!/bin/bash
# test-s3-basic.sh - SeaweedFS S3 基础功能测试

set -e

# 配置
ENDPOINT="http://localhost:8333"
ACCESS_KEY="admin"
SECRET_KEY="key"
BUCKET="test-bucket-$(date +%Y%m%d%H%M%S)"

# 设置 AWS CLI
export AWS_ACCESS_KEY_ID=$ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$SECRET_KEY

echo "=========================================="
echo "SeaweedFS S3 基础功能测试"
echo "=========================================="
echo ""

# 1. 列出 Buckets
echo "1. 测试 ListBuckets..."
aws s3 ls --endpoint-url $ENDPOINT
echo "   ✓ ListBuckets 成功"
echo ""

# 2. 创建 Bucket
echo "2. 测试 CreateBucket..."
aws s3 mb s3://$BUCKET --endpoint-url $ENDPOINT
echo "   ✓ CreateBucket 成功: $BUCKET"
echo ""

# 3. 上传小文件
echo "3. 测试 PutObject (小文件)..."
echo "Hello, SeaweedFS!" > test-small.txt
aws s3 cp test-small.txt s3://$BUCKET/small-file.txt --endpoint-url $ENDPOINT
echo "   ✓ PutObject 成功"
echo ""

# 4. 下载小文件
echo "4. 测试 GetObject (小文件)..."
aws s3 cp s3://$BUCKET/small-file.txt downloaded-small.txt --endpoint-url $ENDPOINT
if grep -q "Hello, SeaweedFS!" downloaded-small.txt; then
    echo "   ✓ GetObject 成功，内容验证通过"
else
    echo "   ✗ GetObject 失败，内容不匹配"
    exit 1
fi
echo ""

# 5. 上传大文件 (100MB)
echo "5. 测试 PutObject (大文件 100MB)..."
dd if=/dev/urandom of=test-large.bin bs=1M count=100 2>/dev/null
aws s3 cp test-large.bin s3://$BUCKET/large-file.bin --endpoint-url $ENDPOINT
echo "   ✓ PutObject (大文件) 成功"
echo ""

# 6. 下载大文件
echo "6. 测试 GetObject (大文件)..."
aws s3 cp s3://$BUCKET/large-file.bin downloaded-large.bin --endpoint-url $ENDPOINT
if cmp -s test-large.bin downloaded-large.bin; then
    echo "   ✓ GetObject (大文件) 成功，内容验证通过"
else
    echo "   ✗ GetObject (大文件) 失败，内容不匹配"
    exit 1
fi
echo ""

# 7. 列出对象
echo "7. 测试 ListObjects..."
aws s3 ls s3://$BUCKET --endpoint-url $ENDPOINT
echo "   ✓ ListObjects 成功"
echo ""

# 8. 删除对象
echo "8. 测试 DeleteObject..."
aws s3 rm s3://$BUCKET/small-file.txt --endpoint-url $ENDPOINT
aws s3 rm s3://$BUCKET/large-file.bin --endpoint-url $ENDPOINT
echo "   ✓ DeleteObject 成功"
echo ""

# 9. 删除 Bucket
echo "9. 测试 DeleteBucket..."
aws s3 rb s3://$BUCKET --endpoint-url $ENDPOINT
echo "   ✓ DeleteBucket 成功"
echo ""

# 清理
rm -f test-small.txt test-large.bin downloaded-small.txt downloaded-large.bin

echo "=========================================="
echo "所有测试通过！✓"
echo "=========================================="
