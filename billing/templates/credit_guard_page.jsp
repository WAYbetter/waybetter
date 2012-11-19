<!-- uncomment for jsp file -->
<!--
<%@ page language="java" contentType="text/html; charset=utf-8"
	pageEncoding="utf-8" errorPage="/error.jsp"%>

<jsp:useBean id="transactionDetails" scope="request" type="com.creditguard.common.transactions.TransactionDetails" />
<%@ include file="/merchantPages/WebSources/includes/main.jsp" %>
-->

<%
String langdir="ltr";
if(lang.equals("HE")){
    langdir="rtl";
}
%>

{% extends "wb_base_site.html" %}
{% load i18n %}
{% block htmlclass %}{{ block.super }} <%=langdir%>{% endblock %}
{% block bodyclass %}{{ block.super }} <%=langdir%>{% endblock %}

{% block extrahead %}
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="cache-control" content="no-cache">
    <meta http-equiv="pragma" content="no-cache">
    <meta http-equiv="expires" content="-1">
    <script src="merchantPages/WebSources/js/<%=lang%>.js"></script>
    <script src="merchantPages/WebSources/js/main.js"></script>
{% endblock %}

{% block extrastyle %}
    <link href='https://fonts.googleapis.com/css?family=Open+Sans' rel='stylesheet' type='text/css'>
    <link href='https://fonts.googleapis.com/css?family=Titillium+Web:400,700italic,700' rel='stylesheet' type='text/css'>
    <link href='/static/css/font-waybetter.css' rel='stylesheet' type='text/css'>

    <% if (lang.equals("HE")) { %>
        <link href="/static/themes/bootstrap-bounce/css/bootstrap.min.rtl.css" rel="stylesheet">
        <link href="/static/themes/bootstrap-bounce/css/font-awesome.rtl.css" rel="stylesheet">
        <!--[if lt IE 8]>
          <link href="/static/themes/bootstrap-bounce/css/font-awesome-ie7.rtl.css" rel="stylesheet">
        <![endif]-->
        <link href="/static/themes/bootstrap-bounce/css/base.rtl.css" rel="stylesheet">
        <link href="/static/themes/bootstrap-bounce/css/blue.rtl.css" rel="stylesheet">
        <link rel="stylesheet" type="text/css" href="/static/css/wb.rtl.css"/>

        <link rel="stylesheet" type="text/css" href="/static/css/wb.rtl.override.css"/>

    <% } else { %>
        <link href="/static/themes/bootstrap-bounce/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/themes/bootstrap-bounce/css/font-awesome.css" rel="stylesheet">
        <!--[if lt IE 8]>
          <link href="/static/themes/bootstrap-bounce/css/font-awesome-ie7.css" rel="stylesheet">
        <![endif]-->
        <link href="/static/themes/bootstrap-bounce/css/base.css" rel="stylesheet">
        <link href="/static/themes/bootstrap-bounce/css/blue.css" rel="stylesheet">
        <link rel="stylesheet" type="text/css" href="/static/css/wb.css"/>
    <% } %>

    <!--[if lt IE 9]>
      <script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script>
    <![endif]-->

    <style type="text/css">
        *{
            direction: <%=langdir%>;
        }

        body{
            padding-bottom: 0;
        }
        .breadcrumb{
            background-color: inherit;
            margin-bottom: 0;
            padding: 5px 0;
        }
        .breadcrumb li{
            color: #999;
        }
        .breadcrumb .active{
            color: inherit;
        }

        #creditForm {
            margin: 0;
        }
        #creditForm input[type="text"]{
            height: auto;
        }
        #creditForm .controls{
            vertical-align: top;
            width: 220px;
        }
        #expiration-date select{
            display: inline-block;
            width: 100px;
        }
        #cvv{
            width: 177px;
        }
        .icon-question-sign{
            font-size: 22px;
            line-height: 18px;
        }
        #wb_CVVhelp{
            display: none;
            width: 225px;
            height: 125px;
            z-index: 1;
            margin-top: 10px;
            background: url("/static/images/wb_site/cvv.png") left 0 no-repeat;
        }

        #safe{
            max-width: 560px;
            margin: 30px auto;
        }

        #certificates{
            width: 644px;
            height: 142px;
            margin: 0 auto 150px auto;
            background: url("/static/images/wb_site/certificates.png") left center no-repeat;
        }
    </style>
{% endblock extrastyle %}

{% block user_tools %}{% endblock %}

{% block headertext %}
    <% if (lang.equals("HE")) { %>
    <i class="icon-lock"></i>
    דף תשלום מאובטח
    <% } else { %>
    Secured Payment Page
    <i class="icon-lock"></i>
    <% } %>
{% endblock %}

{% block content %}
    <div id="content">
        <div class="container">
                <div class="row">
                    <div class="span12">
                        <div class="modal modal-flat">
                            <div class="modal-header pagination-centered">
                                <ul class="breadcrumb">
                                    <li>
                                        <% if (lang.equals("HE")) { %>
                                        פרטי חשבון
                                        <% } else { %>
                                        Account Information
                                        <% } %>
                                        <span class="divider">/</span>
                                    </li>
                                    <li>
                                        <% if (lang.equals("HE")) { %>
                                        אימות טלפון
                                        <% } else { %>
                                        Phone Verification
                                        <% } %>
                                        <span class="divider">/</span>
                                    </li>
                                    <li class="active">
                                        <% if (lang.equals("HE")) { %>
                                        פרטי חיוב
                                        <% } else { %>
                                        Billing Information
                                        <% } %>
                                    </li>
                                </ul>
                            </div>

                            <form id="creditForm" onsubmit="return formValidator(0);" method="POST" action="ProcessCreditCard" class="form-horizontal">
                                <div class="modal-body">
                                    <input type="hidden" name="txId" value="<%=mpiTxnId%>"/>
                                    <input type="hidden" name="lang" value="EN"/>
                                    <input type="hidden" name="track2" value="" autocomplete="off"/>
                                    <input type="hidden" name="last4d" value="" autocomplete="off"/>
                                    <input type="hidden" name="cavv" value="" autocomplete="off"/>
                                    <input type="hidden" name="eci" value="" autocomplete="off"/>
                                    <input type="hidden" name="transactionCode" value="Phone" autocomplete="off"/>

                                    <div class="control-group">
                                        <div class="control-label"><%=CCNumber%></div>
                                        <div class="controls"><input type="text" id="cardNumber" name="cardNumber" maxlength="19" autocomplete="off"/></div>
                                    </div>
                                    <div class="control-group" id="expiration-date">
                                        <div class="control-label"><%=CCExp%></div>
                                        <div class="controls">
                                            <select id="expYear" name="expYear" class="pull-right">
                                                <%=expYear%>
                                            </select>
                                            <select id="expMonth" name="expMonth" class="pull-left">
                                                <option value="01">01</option>
                                                <option value="02">02</option>
                                                <option value="03">03</option>
                                                <option value="04">04</option>
                                                <option value="05">05</option>
                                                <option value="06">06</option>
                                                <option value="07">07</option>
                                                <option value="08">08</option>
                                                <option value="09">09</option>
                                                <option value="10">10</option>
                                                <option value="11">11</option>
                                                <option value="12">12</option>
                                            </select>

                                            <div class="clearfix"></div>
                                        </div>
                                    </div>

                                    <div class="control-group">
                                        <div class="control-label">CVV</div>
                                        <div class="controls">
                                            <div class="input-append">
                                                <input type="text" name="cvv" id="cvv" maxlength="4" autocomplete="off"/>
                                                <span class="add-on" id="qm"><i class="icon-question-sign"></i></span>
                                            </div>
                                            <div id="wb_CVVhelp"></div>
                                        </div>
                                    </div>

                                    <div class="control-group">
                                        <div class="control-label"><%=CCPId%></div>
                                        <div class="controls">
                                            <input type="text" id="personalId" name="personalId" maxlength="9" autocomplete="off"/>
                                        </div>
                                    </div>
                                </div>


                                <div class="modal-footer">
                                    <input type="submit" class="btn btn-primary pull-right" id="submitBtn" value="<%=formSend%>"/>
                                    <input id="resetBtn" type="reset" style="display: none" value="<%=formReset%>"/>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>

            <div id="safe">
                <strong>
                    <% if (lang.equals("HE")) { %>
                    אתה בטוח:
                    <% } else { %>
                    You are safe:
                    <% } %>
                </strong>
                <br>
                <% if (lang.equals("HE")) { %>
                WAYbetter אינה מחזיקה בפרטי האשראי שלך. פרטי האשראי נשמרים בצורה מאובטחת בחברת Credit
                Guard.
                <% } else { %>
                WAYbetter does not store nor hold any of your details. You are professionally secured with Credit
                Guard
                <% } %>

            </div>
            <div id="certificates"></div>
        </div>
    </div>
{% endblock %}

{% block footer %}{% endblock %}

{% block scripts %}{% endblock %}
{% block doc_ready %}
    <script type="text/javascript">
        $(function() {
            $("#wb-logo").attr("href", "http://www.waybetter.com");  // in context of this page '/' links to creditguard
            $("#cardNumber").hide();  // fix weird rendering bug in chrome
            $("#cardNumber").show();
            $("#qm").bind("mouseover mouseout", function() {
                var $help = $("#wb_CVVhelp");
                if ($help.is(":visible")) {
                    $help.hide();
                }
                else {
                    $help.show();
                }
            });
        })
    </script>
{% endblock %}