from statistics import mean, pstdev

def compute_trajectory(history: dict[str, list[int]], soften: bool = False, war_stage: str = None) -> dict[str, float]:
    from core.engines.war_stage_detector import war_stage_detector
    scores_dict = {}

    # Get stage-based weights
    weights = war_stage_detector.get_stage_weights(war_stage) if war_stage else {
        'momentum': 0.6,
        'stability': 0.3,
        'output': 0.1
    }

    for player, scores in history.items():
        if len(scores) < 2:
            scores_dict[player] = 0.0
            continue
        last = scores[-1]
        avg = mean(scores)
        variance = pstdev(scores) if len(scores) > 2 else 0.0001
        momentum = (last - avg) / max(avg, 1)
        stability = 1 / (variance + 0.001)
        output_index = last / max(avg, 1)
        trajectory = (momentum * weights['momentum'] + 
                     stability * weights['stability'] + 
                     output_index * weights['output'])
        if soften:
            trajectory *= 0.85
        scores_dict[player] = trajectory
    # Sort by highest trajectory first
    sorted_scores = dict(sorted(scores_dict.items(), key=lambda x: x[1], reverse=True))
    return sorted_scores
