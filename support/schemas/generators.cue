package problemformat

// To validate generators.yaml using cue:
// > cue vet generators.yaml *.cue -d "#Generators"

import "struct"

#command: !="" & (=~"^[^{}]*(\\{(name|seed(:[0-9]+)?)\\}[^{}]*)*$")
#file_config: {
	solution?:    #command // null disallowed (specify #testcase.ans instead)
	visualizer?:  #command | null // null means: skip visualisation
	random_salt?: string
}

#testcase: 
	#command |            // same as create: #command
	null |                // deprecated
	{
		generate?: #command // invocation of a generator
		copy?:     #path 
		["in" | "ans" | "desc" | "hint" ]: string // explicit contents
		#file_config
	} 

#data_dict: [string]: #testgroup | #testcase

#testgroup: {
	#file_config
	"testdata.yaml"?: #testdata_settings                                   // TODO should this field be testdata_settings or settings?
	data:             #data_dict | [...{#data_dict & struct.MaxFields(1)}] // list of singleton dicts
}

#Generators: {
	generators?: [string]: [...string]
	#testgroup
	... // Do allow unknown_key at top level for tooling
} 

#Generators: data: close({
		// Restrict top level data to testgroups 'sample', 'secret'
		sample: #testgroup
		secret: #testgroup
	})
