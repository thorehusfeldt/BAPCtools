// Below is a formal [CUE](https://cuelang.org/docs/references/spec/)
// specification for the `generators.yaml` file with a root object `Generators`.
//
// The `...` in `generator` and `directory` indicate that additional keys
// unknown to the spec are allowed.
// The `generator_reserved` and `directory_reserved` objects indicate keys that
// work only for `generator`/`directory` and should not be reused in other places.
import "list"
import "strconv"

command: !="" & (=~"^[^{}]*(\\{(name|seed(:[0-9]+)?)\\}[^{}]*)*$")
file_config: {
    solution?: command | null
    visualizer?: command | null
    random_salt?: string
}
generator: command | {
    input: command
    file_config
    directory_reserved
    ...
}
data_dict: {
    [string]: directory | generator | null
}
directory: {
    file_config
    "testdata.yaml"?: {
        ...
    }
    data?: data_dict | [...data_dict]
    generator_reserved
    ...
}


Generators: Constraints & {
    generators?: {
        [string]: [...string]
    }
    directory
}
generator_reserved: {
    input?: _|_
    ...
}
directory_reserved: {
    data?: _|_
    include?: _|_
    "testdata.yaml"?: _|_
    ...
}

Constraints: {
    "testdata.yaml": {
        on_reject: "continue"
	range: data.secret."testdata.yaml".range
	grader_flags: "first_error"
    }
    data: sample: "testdata.yaml": {
        on_reject: "continue"
	range: "0 0"
	accept_score: "0"
	grader_flags: "first_error"
    }
    data: secret: "testdata.yaml": {
        on_reject: "continue"
	range: "0 \(list.Sum([for group in data.secret.data { strconv.Atoi(group."testdata.yaml".accept_score)}]))"
	grader_flags: "first_error accept_if_any_accepted"
    }
    data: secret: data: [string]: "testdata.yaml": {
        on_reject: "break"
	accept_score: =~ "[1-9][0-9]*"
	range: "0 \(accept_score)"
	grader_flags: "min"
    }
}

