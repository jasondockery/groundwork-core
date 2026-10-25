# Local model workflows · Groundwork

Running a model locally can support agent-assisted work while inference stays on your device. This guide helps you evaluate the model, runtime, data boundary, and hardware fit. The environment repositories own installation and machine-specific instructions.

## Understand what you are choosing

An open-weight model makes its trained parameters available, but the term does not mean the model is open source in every sense or unrestricted. Check the exact model's license and publisher terms before selecting it. The model, inference runtime, tokenizer, adapter, and any converted or quantized files can have separate sources and terms.

A model card is the publisher's description of intended uses, limits, and evaluations. Read it alongside the license. Confirm who published the exact model files, which revision you are using, and whether a conversion came from a source you can verify. Check published hashes when available. Review any downloaded code before allowing a runtime to execute it.

## Match the model to a real task and device

Start with a task you expect the model to help with, such as explaining a repository change or drafting a test. Try that task with representative inputs and judge the result yourself. If an agent will use tools, verify the exact tool-use behavior too. A compatible API or a high benchmark score alone does not prove the workflow works.

Model file size is only part of the resource cost. The runtime also needs memory for context, temporary work, and the rest of the applications on your machine. Leave headroom, especially on devices that share memory between the CPU and GPU. Quantization can reduce file and memory needs, with possible changes to output quality. Confirm that the runtime actually supports the device and acceleration path you intend to use. Record the backend the running process reports. A build that can use a GPU can still fall back to CPU.

Record practical task success, output quality, latency, memory and disk use, and offline behavior. Compare the result with the task's requirements, not only with a general benchmark. Recheck the choice when the model, runtime, backend, operating system, or hardware changes. Treat model and runtime recommendations as dated findings, not permanent defaults.

## Keep the data boundary clear

Local describes where inference runs. It does not guarantee that every part of an application stays on the device. A client may send prompts or metadata to a hosted provider, save history or logs, synchronize data, or use online tools. Check the behavior of the runtime, application, provider configuration, and any tools attached to an agent.

Do not enter information that your device, workplace, or provider policy does not allow. Check where prompts, outputs, caches, and logs are stored, how long they remain, and how to remove them. A local model does not gain authority over files or commands by itself. Keep agent tools scoped to the task, and review generated commands or code before running them. A local-to-hosted fallback changes where data goes; leave it disabled unless the user explicitly chooses it and the applicable policy permits it.

## Keep the choice optional and traceable

Local inference is optional. It leaves existing cloud-provider apps, CLIs, and their sign-in unchanged unless the person opts into a local runtime for a specific task. Model downloads can be large. Show the source and expected disk use before an explicit download, and leave enough free space for the runtime and its working data. A runtime's preset model on the first chat or generate command is still a download. Show the source and size and wait for an explicit choice before that first run. Do not install a runtime, select a model, or download weights as a side effect of normal machine setup. Keep model files outside Git repositories.

For a useful evaluation record, note:

- The date, device, operating system, runtime and version, and effective backend.
- The model publisher, exact revision and file, license source, and any conversion or quantization.
- The task you evaluated and the observed quality, tool behavior, latency, memory, disk, and offline behavior.
- How to stop the runtime, update or replace the model, and remove downloaded files and local history.

The platform setup belongs with each environment: [groundwork-mac](https://github.com/jasondockery/groundwork-mac) ([issue 41](https://github.com/jasondockery/groundwork-mac/issues/41)) owns the Mac workflow, and [groundwork-omarchy-mac-arm64](https://github.com/jasondockery/groundwork-omarchy-mac-arm64) ([issue 36](https://github.com/jasondockery/groundwork-omarchy-mac-arm64/issues/36)) owns the Omarchy workflow. Those issue links stand until the repositories publish a page. Retarget them to the published pages. Follow those repositories for supported runtime choices and installation, update, and removal steps. This shared guide does not select one model or backend for every machine.
