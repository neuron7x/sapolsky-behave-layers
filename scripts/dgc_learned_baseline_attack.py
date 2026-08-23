from cwc.governance.learned_baseline import CalibrationExample, LearnedRouterConfig, fit_learned_router


def cfg():
    return LearnedRouterConfig(("x",),("a","b"),0.1,1.0,0.1,1.0)


def rows():
    return [
        CalibrationExample("t1","a",(0.0,),1.0,0.1,0.0),
        CalibrationExample("t1","b",(0.0,),0.9,0.5,0.0),
        CalibrationExample("t2","a",(1.0,),0.2,0.1,0.5),
        CalibrationExample("t2","b",(1.0,),1.0,0.5,0.0),
    ]


def main():
    killed=0
    try:
        fit_learned_router(cfg(),rows(),forbidden_task_ids=("t2",))
    except ValueError:
        killed+=1
    try:
        fit_learned_router(cfg(),rows()[:-1])
    except ValueError:
        killed+=1
    duplicated=rows(); duplicated.append(duplicated[0])
    try:
        fit_learned_router(cfg(),duplicated)
    except ValueError:
        killed+=1
    try:
        CalibrationExample("bad","a",(0.0,),1.1,0.1,0.0)
    except ValueError:
        killed+=1
    if killed!=4:
        raise AssertionError(f"expected 4/4 attacks killed, got {killed}")
    print("DGC-LEARNED-BASELINE-ATTACK: PASS killed=4/4")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
