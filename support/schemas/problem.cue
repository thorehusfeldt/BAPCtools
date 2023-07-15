#problem_settings: {
    // Should these fields all also accept null? If so, what's the semantics of, say,
    //     license:
    // TODO: typical-problem.yaml violates spec (name missing)
    // TODO: maximal-problem.yaml violates spec (name missing, validator should be validator_flags)
    name: string | { [string]: string }
    type?: *"pass-fail" | "scoring"
    author?: string
    source?: string
    if source != _|_ { source_url?: string } # only allow source_url if source is specified
    license?: *"unknown" | "public domain" | "cc0" | "cc by" | "cc by-sa" | "educational" | "permission"
    rights_owner?: string
    limits?: #limits
    validation?: *"default" | #custom_validation
    validator_flags?: string
    scoring?: {
        objective: *"max" | "min"
        show_test_data_groups: *false | true
    }
    keywords?: string | [...string]
    uuid?: string
    languages?: string | [...string]
}

#custom_validation: this={
    string
    _as_struct: { for w in strings.Split(this, " ")  { (w): _ } }
    _as_struct: close({ 
        custom: _,       // Must include "custom",
        score?: _,       // can include "score" ...
        interactive?: _  // ... and "interactive"
})
}

#limits: { 
    // All are optional, right?
    // Is the empty limits dictionary valid? (I guess yes)
    // TODO: are these all ints?
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
