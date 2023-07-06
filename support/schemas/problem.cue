#problem_settings: {
    // Should these fields all also accept null? If so, what's the semantics of, say,
    //     license:
    // TODO: typical-problem.yaml violates spec (name missing)
    // TODO: maximal-problem.yaml violates spec (name missing, validator should be validator_flags)
    name: string | { [string]: string }
    type: *"pass-fail" | "scoring"
    author?: string
    source?: string
    source_url?: string
    if source == null { source_url: null }
    license?: *"unknown" | "public domain" | "cc0" | "cc by" | "cc by-sa" | "educational" | "permission"
    rights_owner?: string
    limits?: #limits
    validation: *"default" | 
        "custom" |
        "custom interactive" | 
        "custom score" | 
        "custom interactive score"
    validator_flags?: string
    scoring: {
        objective: *"max" | "min"
        show_test_data_groups: *false | true
    }
    keywords?: string | [...string]
    uuid?: string
    languages?: string | [...string]
}

#limits: { 
    // all are optional, right?
    // is the empty limits dictionary valid? (I guess yes)
    time_multiplier?: *5 | int
    time_safety_margin?: *2 | int
    memory?: int
    output?: int
    code?: int
    compilation_time?: int
    compilation_memory?: int
    validation_time?: int
    validation_memory?: int
    validation_output?: int
}