#!/usr/bin/env python3
import subprocess
import sys

def main():
    print('Building Docker image...')
    result = subprocess.run(['docker', 'build', '-t', 'myapp:latest', '.'])
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
