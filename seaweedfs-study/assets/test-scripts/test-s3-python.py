#!/usr/bin/env python3
# test-s3-python.py - SeaweedFS S3 Python SDK 测试

import boto3
import os
import hashlib
import time
from botocore.exceptions import ClientError

# 配置
ENDPOINT = 'http://localhost:8333'
ACCESS_KEY = 'admin'
SECRET_KEY = 'key'
BUCKET = f'test-bucket-{int(time.time())}'

def get_s3_client():
    """创建 S3 客户端"""
    return boto3.client(
        's3',
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='us-east-1'
    )

def test_bucket_operations():
    """测试 Bucket 操作"""
    print("\n=== 测试 Bucket 操作 ===")
    s3 = get_s3_client()
    
    # CreateBucket
    print("1. CreateBucket...", end=' ')
    s3.create_bucket(Bucket=BUCKET)
    print("✓")
    
    # ListBuckets
    print("2. ListBuckets...", end=' ')
    response = s3.list_buckets()
    assert any(b['Name'] == BUCKET for b in response['Buckets'])
    print("✓")
    
    # HeadBucket
    print("3. HeadBucket...", end=' ')
    s3.head_bucket(Bucket=BUCKET)
    print("✓")
    
    return s3

def test_object_operations(s3):
    """测试 Object 操作"""
    print("\n=== 测试 Object 操作 ===")
    
    # PutObject (小文件)
    print("1. PutObject (小文件)...", end=' ')
    s3.put_object(Bucket=BUCKET, Key='small.txt', Body=b'Hello, SeaweedFS!')
    print("✓")
    
    # GetObject
    print("2. GetObject...", end=' ')
    response = s3.get_object(Bucket=BUCKET, Key='small.txt')
    content = response['Body'].read()
    assert content == b'Hello, SeaweedFS!'
    print("✓")
    
    # HeadObject
    print("3. HeadObject...", end=' ')
    response = s3.head_object(Bucket=BUCKET, Key='small.txt')
    assert 'ContentLength' in response
    print("✓")
    
    # ListObjects
    print("4. ListObjects...", end=' ')
    response = s3.list_objects_v2(Bucket=BUCKET)
    assert response['KeyCount'] == 1
    print("✓")
    
    # CopyObject
    print("5. CopyObject...", end=' ')
    s3.copy_object(
        Bucket=BUCKET,
        CopySource={'Bucket': BUCKET, 'Key': 'small.txt'},
        Key='small-copy.txt'
    )
    print("✓")
    
    # DeleteObjects (批量)
    print("6. DeleteObjects...", end=' ')
    s3.delete_objects(
        Bucket=BUCKET,
        Delete={'Objects': [{'Key': 'small.txt'}, {'Key': 'small-copy.txt'}]}
    )
    print("✓")
    
    print("所有 Object 操作测试通过！")

def test_multipart_upload(s3):
    """测试分片上传"""
    print("\n=== 测试分片上传 ===")
    
    # 创建 50MB 测试文件
    file_size = 50 * 1024 * 1024
    file_name = 'test-multipart.bin'
    key_name = 'multipart-test.bin'
    
    print(f"1. 创建 {file_size // 1024 // 1024}MB 测试文件...", end=' ')
    with open(file_name, 'wb') as f:
        f.write(b'0' * file_size)
    print("✓")
    
    # 计算 MD5
    print("2. 计算原始 MD5...", end=' ')
    md5 = hashlib.md5()
    with open(file_name, 'rb') as f:
        md5.update(f.read())
    original_md5 = md5.hexdigest()
    print(f"✓ ({original_md5[:8]}...)")
    
    # 分片上传
    print("3. 分片上传...", end=' ')
    from boto3.s3.transfer import TransferConfig
    config = TransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        multipart_chunksize=8 * 1024 * 1024,
        max_concurrency=4,
        use_threads=True
    )
    s3.upload_file(file_name, BUCKET, key_name, Config=config)
    print("✓")
    
    # 验证
    print("4. 验证上传结果...", end=' ')
    response = s3.head_object(Bucket=BUCKET, Key=key_name)
    assert response['ContentLength'] == file_size
    print("✓")
    
    # 下载验证
    print("5. 下载并验证 MD5...", end=' ')
    s3.download_file(BUCKET, key_name, 'downloaded-multipart.bin')
    md5 = hashlib.md5()
    with open('downloaded-multipart.bin', 'rb') as f:
        md5.update(f.read())
    downloaded_md5 = md5.hexdigest()
    assert original_md5 == downloaded_md5
    print("✓")
    
    # 清理
    os.remove(file_name)
    os.remove('downloaded-multipart.bin')
    s3.delete_object(Bucket=BUCKET, Key=key_name)
    
    print("分片上传测试通过！")

def test_presigned_url(s3):
    """测试预签名 URL"""
    print("\n=== 测试预签名 URL ===")
    
    # 上传测试文件
    print("1. 上传测试文件...", end=' ')
    s3.put_object(Bucket=BUCKET, Key='presigned-test.txt', Body=b'Test Content')
    print("✓")
    
    # 生成预签名 URL
    print("2. 生成预签名 URL...", end=' ')
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET, 'Key': 'presigned-test.txt'},
        ExpiresIn=3600
    )
    print(f"✓")
    print(f"   URL: {url[:60]}...")
    
    # 验证 URL 可访问
    print("3. 验证 URL 可访问...", end=' ')
    import requests
    response = requests.get(url)
    assert response.content == b'Test Content'
    print("✓")
    
    # 清理
    s3.delete_object(Bucket=BUCKET, Key='presigned-test.txt')
    
    print("预签名 URL 测试通过！")

def cleanup(s3):
    """清理测试资源"""
    print("\n=== 清理测试资源 ===")
    print("删除 Bucket...", end=' ')
    s3.delete_bucket(Bucket=BUCKET)
    print("✓")

def main():
    """主测试函数"""
    print("=" * 60)
    print("SeaweedFS S3 Python SDK 测试")
    print("=" * 60)
    
    try:
        # 运行测试
        s3 = test_bucket_operations()
        test_object_operations(s3)
        test_multipart_upload(s3)
        test_presigned_url(s3)
        
        # 清理
        cleanup(s3)
        
        print("\n" + "=" * 60)
        print("所有测试通过！✓")
        print("=" * 60)
        
    except ClientError as e:
        print(f"\n✗ S3 错误：{e}")
        return 1
    except Exception as e:
        print(f"\n✗ 未知错误：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
