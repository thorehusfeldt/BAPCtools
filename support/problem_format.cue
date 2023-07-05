package problemformat

import "strings"
import "strconv"

#testdata_settings: {
	on_reject?: "break" | "continue"
	grading?: "default" | "custom"
	grader_flags?: string
//	if grading != "custom" { grader_flags? : #default_grader_flags }
	input_validator_flags?: string
	output_validator_flags?: string
	accept_score?: #score
	reject_score?: #score
	range?: #range 
}
// matches "1", "06", "21", ".4", "-1.2", but not 'inf'
#score: =~ "^-?([0-9]+|[0-9]*.[0-9]+)$" 

// matches "-inf 5", "0 100", "1.4 1.7", "6 6", but not "5 1"
#range: this={
    string
    _valid: strings.Split(this, " ") & [#score, #score]       // two space-separated #scores
    _lo: strconv.ParseFloat(strings.Split(this, " ")[0], 64)  // parses to float (including '-inf')
    _hi: strconv.ParseFloat(strings.Split(this, " ")[1], 64)
    _order: true & _lo <= _hi
}

// TOOD: Could also enforce relations between accept_score and range

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