"""
FastAPI backend tying the pipeline together:
  GET  /api/tasks     -> current tasks (scored)
  GET  /api/trains    -> current trains
  POST /api/optimize  -> run the CP-SAT optimizer, create a Block
  GET  /api/blocks    -> current blocks
  POST /api/check-conflicts -> run the conflict monitor against the latest block
  GET  /api/alerts    -> alerts raised so far
  POST /api/reset     -> reseed the demo scenario from scratch
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from models import get_engine, init_db, Task, Train, Block, Alert, BlockStatus
from data_generator import seed_demo_scenario
from priority_engine import score_all
from optimizer import optimize_into_single_block
from conflict_monitor import run_monitor_once

app = FastAPI(title="Railway Block Planning Prototype")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = get_engine()
Session = init_db(engine)


def get_session():
    return Session()


@app.post("/api/reset")
def reset():
    session = get_session()
    tasks, trains = seed_demo_scenario(session)
    session.close()
    return {"status": "reseeded", "tasks": len(tasks), "trains": len(trains)}


@app.get("/api/tasks")
def get_tasks():
    session = get_session()
    tasks = session.query(Task).all()
    if not tasks:
        session.close()
        return []
    score_all(tasks)
    session.commit()
    result = [
        {
            "id": t.id, "department": t.department.value, "section": t.section,
            "defect_desc": t.defect_desc, "severity": t.severity.value,
            "overdue_days": t.overdue_days, "est_duration_min": t.est_duration_min,
            "priority_score": t.priority_score, "block_id": t.block_id,
        }
        for t in tasks
    ]
    session.close()
    return result


@app.get("/api/trains")
def get_trains():
    session = get_session()
    trains = session.query(Train).all()
    result = [
        {
            "id": tr.id, "number": tr.number, "section": tr.section,
            "priority": tr.priority.value,
            "scheduled_pass_time": tr.scheduled_pass_time.isoformat(),
            "actual_pass_time": tr.actual_pass_time.isoformat() if tr.actual_pass_time else None,
            "slack_minutes": tr.slack_minutes, "is_late": tr.is_late,
        }
        for tr in trains
    ]
    session.close()
    return result


@app.post("/api/optimize")
def run_optimize(section: str = "SEC-14"):
    session = get_session()
    tasks = session.query(Task).filter(Task.section == section).all()
    if not tasks:
        session.close()
        raise HTTPException(404, f"No tasks found for section {section}")

    score_all(tasks)
    session.commit()

    day_start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    result = optimize_into_single_block(tasks, day_start)
    if result is None:
        session.close()
        raise HTTPException(500, "Solver could not find a feasible schedule")

    block_start, block_end, ordered_ids = result

    # Clear any previous block for this section (demo keeps a single active block)
    old_blocks = session.query(Block).filter(Block.section == section).all()
    for ob in old_blocks:
        session.query(Task).filter(Task.block_id == ob.id).update({"block_id": None})
        session.delete(ob)
    session.commit()

    block = Block(section=section, start_time=block_start, end_time=block_end, status=BlockStatus.OPTIMIZED)
    session.add(block)
    session.flush()
    for tid in ordered_ids:
        session.query(Task).filter(Task.id == tid).update({"block_id": block.id})
    session.commit()

    response = {
        "block_id": block.id,
        "section": section,
        "start_time": block_start.isoformat(),
        "end_time": block_end.isoformat(),
        "task_count_before": len(tasks),
        "block_count_after": 1,
        "reduction_pct": round((1 - 1 / len(tasks)) * 100),
        "ordered_task_ids": ordered_ids,
    }
    session.close()
    return response


@app.get("/api/blocks")
def get_blocks():
    session = get_session()
    blocks = session.query(Block).all()
    result = [
        {
            "id": b.id, "section": b.section, "status": b.status.value,
            "start_time": b.start_time.isoformat(), "end_time": b.end_time.isoformat(),
            "task_ids": [t.id for t in b.tasks],
        }
        for b in blocks
    ]
    session.close()
    return result


@app.post("/api/check-conflicts")
def check_conflicts(section: str = "SEC-14"):
    session = get_session()
    block = session.query(Block).filter(Block.section == section).first()
    if not block:
        session.close()
        raise HTTPException(404, "No active block \u2014 run /api/optimize first")

    trains = session.query(Train).filter(Train.section == section).all()
    alerts = run_monitor_once(session, block, trains)
    result = [
        {"train_id": a.train_id, "action": a.action_taken, "message": a.message}
        for a in alerts
    ]
    session.close()
    return result


@app.get("/api/alerts")
def get_alerts():
    session = get_session()
    alerts = session.query(Alert).order_by(Alert.created_at.desc()).all()
    result = [
        {
            "id": a.id, "block_id": a.block_id, "train_id": a.train_id,
            "message": a.message, "action_taken": a.action_taken,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]
    session.close()
    return result


@app.get("/")
def root():
    return {"status": "ok", "message": "Railway Block Planning prototype API"}
