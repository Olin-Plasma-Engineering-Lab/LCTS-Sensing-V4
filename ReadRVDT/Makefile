filename = ReadRVDT

build:
	dotnet publish ${filename}.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o .\publish

clean: