console.log('mysearch.js is integrated!')

class SearchBar {
    constructor(index, api_key, parameter) {
        this.index = index;
        this.api_key = api_key;
        this.parameter = parameter
        console.log("created SearchBar")
    }    
    start(div_id) {
        console.log(this.index + " " + this.api_key + " " + this.parameter);
        var that = this
        var search_div = document.getElementById(div_id);
        if(search_div == null)
            console.log(div_id + " Not Found");
        else 
        {
            console.log("div_id correct");

            var search_element = document.createElement("INPUT");
            search_div.appendChild(search_element)
            search_element.setAttribute("type", "text");

            var result_element = document.createElement("DIV")
            search_div.appendChild(result_element)

            search_element.oninput = function getSearchResults() {
                var search_value = search_element.value;
                console.log(search_value);
                var url = "http://localhost:5000/search/"+that.api_key+"/"+that.index+"?"+that.parameter+"=";
                url = url + search_value;

                response = fetch(url)
                    .then(response =>{
                        return (response.json())
                    })
                    .then(data =>{
                        var text = "";
                        for (var i = 0; i < data.length; i++) {
                            text += data[i]['_source']['title'] + "<br>";
                        }
                        result_element.innerHTML = text;
                    })    
            }
        }
        
    }
}