import asyncio
import os
import sys
import aiohttp

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tfbrkdiowzzkhgtdmxlj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    print("❌ ERROR: SUPABASE_SERVICE_ROLE_KEY env var is required to delete Auth users.")
    sys.exit(1)

async def _supabase_request(session, method: str, path: str, is_auth: bool = False):
    url = f"{SUPABASE_URL}/auth/v1{path}" if is_auth else f"{SUPABASE_URL}/rest/v1{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    async with session.request(method, url, headers=headers) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise Exception(f"Error {resp.status}: {text[:200]}")
        
        if text.strip() and resp.status != 204:
            import json
            return json.loads(text)
        return {}


async def cleanup():
    print(f"🔍 Searching for stress agents in {SUPABASE_URL}...")
    
    async with aiohttp.ClientSession() as session:
        # We look for agents with emails starting with 'stressagent'
        try:
            agents = await _supabase_request(session, "GET", "/agents?email=like.stressagent*&select=id,email,name")
            
            if not agents:
                print("✅ No stress agents found in the 'agents' table.")
                return

            print(f"📦 Found {len(agents)} stress agents to clean up:")
            for a in agents:
                print(f"  - {a['email']} (ID: {a['id']})")
                
            print("\n🧹 Starting cleanup process...")
            
            deleted_count = 0
            for agent in agents:
                agent_id = agent["id"]
                
                # 1. Delete from agent_devices
                try:
                    await _supabase_request(session, "DELETE", f"/agent_devices?agent_id=eq.{agent_id}")
                except Exception as e:
                    print(f"  ⚠️ Warning: Could not delete devices for {agent_id}: {e}")
                    
                # 2. Delete from agents
                try:
                    await _supabase_request(session, "DELETE", f"/agents?id=eq.{agent_id}")
                except Exception as e:
                    print(f"  ⚠️ Warning: Could not delete from agents table for {agent_id}: {e}")
                
                # 3. Delete from auth.users (requires service_role key)
                try:
                    # Admin delete user API
                    await _supabase_request(session, "DELETE", f"/admin/users/{agent_id}", is_auth=True)
                    deleted_count += 1
                except Exception as e:
                    print(f"  ⚠️ Warning: Could not delete Auth user {agent_id}: {e}")
                    
            print(f"\n✅ Successfully completely removed {deleted_count}/{len(agents)} stress agents.")
            
        except Exception as e:
            print(f"💥 Fatal error during cleanup: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup())
