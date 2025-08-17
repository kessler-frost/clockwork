#!/usr/bin/env python3
import subprocess
import sys
import os

def main():
    print('Building Docker image...')
    context = os.environ.get('APP_WORKDIR', '.')
    tag = os.environ.get('IMAGE_TAG', 'myapp:latest')
    
    cmd = ['docker', 'build', '-t', tag, context]
    print(f'Running: {" ".join(cmd)}')
    
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f'Image {tag} built successfully')
    else:
        print(f'Failed to build image {tag}')
        
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
