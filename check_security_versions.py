"""
Security Verification Script
Checks that all critical dependencies are at secure versions
"""

import sys
from importlib.metadata import version

# Minimum secure versions
SECURE_VERSIONS = {
    'fastapi': '0.115.0',
    'starlette': '0.41.0',
    'uvicorn': '0.32.0',
    'cryptography': '44.0.0',
    'aiohttp': '3.11.0',
    'PyJWT': '2.10.0',
    'bcrypt': '4.2.0',
    'httpx': '0.28.0',
    'openai': '1.58.0',
    'pytest': '8.3.0',
    'jinja2': '3.1.5',
    'werkzeug': '3.1.0',
}

def check_versions():
    """Check if installed packages meet minimum secure versions"""
    print("🔒 Security Version Check\n" + "="*50)
    
    all_secure = True
    for package, min_version in SECURE_VERSIONS.items():
        try:
            installed = version(package)
            is_secure = _compare_versions(installed, min_version)
            
            status = "✅" if is_secure else "❌"
            print(f"{status} {package:20} {installed:15} (min: {min_version})")
            
            if not is_secure:
                all_secure = False
        except Exception as e:
            print(f"⚠️  {package:20} NOT INSTALLED")
            all_secure = False
    
    print("="*50)
    if all_secure:
        print("✅ All packages are at secure versions!")
        return 0
    else:
        print("❌ Some packages need updates!")
        print("\nRun: pip install --upgrade -r requirements.txt")
        return 1

def _compare_versions(installed, minimum):
    """Simple version comparison"""
    try:
        inst_parts = [int(x) for x in installed.split('.')[:3]]
        min_parts = [int(x) for x in minimum.split('.')[:3]]
        
        # Pad with zeros if needed
        while len(inst_parts) < 3:
            inst_parts.append(0)
        while len(min_parts) < 3:
            min_parts.append(0)
        
        return inst_parts >= min_parts
    except:
        return False

if __name__ == "__main__":
    sys.exit(check_versions())
