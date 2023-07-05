package problemformat

import "strings"

#testdata_settings: {
	on_reject?: "break" | "continue"
	grading?: "default" | "custom"
	grader_flags?: string
//	if grading != "custom" { grader_flags? : #default_grader_flags }
	input_validator_flags?: string
	output_validator_flags?: string
	accept_score?: #score
	reject_score?: #score
	range?: string // could be much improved, good CUE exercise
}

#score: =~ "^-?([0-9]+|[0-9]*.[0-9]+)$" // matches "1", "06", "21", ".4", "1.2", even negatives
#filename: =~ "^[a-zA-Z0-9][a-zA-Z0-9_.-]*[a-zA-Z0-9]$"
#path: =~ "[a-zA-Z0-9_.-/]*"

// Default grader
// --------------

#default_grader_flags: this={
    string  
    _as_struct: { for w in strings.Split(this, " ")  { (w): _ } }  // convert to struct and ...
    _as_struct: #valid_default_grader_fields                       // ... validate its fields
    }

// Default grader flags (converted to fields of a CUE struct for validation)
#valid_default_grader_fields: {
    #verdict_aggregation_mode?   // at most one verdict aggregation mode
    #score_aggregation_mode?     // at most one score aggregation mode
    ignore_sample?: _            // two more optional flags
    accept_if_any_accepted?: _
}

#verdict_aggregation_mode: {first_error: _ } | *{worst_error: _  } | {always_accept: _ }
#score_aggregation_mode:  {min: _ } | {max: _ } | *{sum: _ } | {avg: _ }