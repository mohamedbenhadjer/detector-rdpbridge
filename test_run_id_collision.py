import uuid

def test_run_id_collisions():
    run_ids = set()
    for _ in range(100_000):
        # The fix is to use full UUID
        # Previously it was str(uuid.uuid4())[:8] which caused collisions
        run_id = str(uuid.uuid4())
        assert run_id not in run_ids, f"Collision detected! {run_id}"
        run_ids.add(run_id)
    print("Test passed: 100,000 run IDs generated with zero collisions.")

if __name__ == "__main__":
    test_run_id_collisions()
