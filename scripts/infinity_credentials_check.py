import os
import requests

def verify_credentials():
    """Verify your Infinity credentials are working"""
    base_url = "https://ipgrp.infinityfleet.net" #os.getenv("INFINITY_BASE_URL")
    token = "aflbIuIef9s/srht3pjgE2CDQmIaPk1VttHW" #os.getenv("INFINITY_TOKEN")
    
    if not base_url or not token:
        print("❌ Missing environment variables!")
        print("   Set INFINITY_BASE_URL and INFINITY_TOKEN")
        return False
    
    # Test with a simple vesselsws call (PDF page 39)
    endpoint = f"{base_url}/pub/ws/vesselsws.php"
    soap_action = "InfinityVesselsWsdl#getVesselsInfo"
    
    headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "Accept": "application/soap+xml",
        "SOAPAction": f'"{soap_action}"',
        "x-http-auth": token
    }
    
    body = """<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
        <Body>
            <getVesselsInfo xmlns="InfinityVesselsWsdl"/>
        </Body>
    </Envelope>"""
    
    try:
        response = requests.post(endpoint, data=body, headers=headers, verify=True)
        response.raise_for_status()
        
        print("✅ Authentication successful!")
        print(f"   Base URL: {base_url}")
        print(f"   Token: {token[:10]}...")
        print(f"\n   Response preview:")
        print(f"   {response.text[:300]}...")
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("❌ Authentication failed!")
            print("   Check your token is correct")
            print("   Check token has 'Vessels Web Service' permission enabled")
        else:
            print(f"❌ HTTP Error: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print(f"   Check your INFINITY_BASE_URL is correct")
        return False

if __name__ == "__main__":
    verify_credentials()
