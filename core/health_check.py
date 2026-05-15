import os
def check():
    if os.path.exists("/tmp/sports_edge_scheduler.lock"):
        return "✅ Scheduler está rodando."
    return "❌ Scheduler parou."

if __name__ == "__main__":
    print(check())
